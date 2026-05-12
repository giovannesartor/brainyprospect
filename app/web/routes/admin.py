"""Painel admin: usuários, configurações globais, saúde, logs."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import and_, desc, func, select

from app.config.settings_manager import (
    Settings,
    get_settings,
    update_settings,
)
from app.database.db import IS_POSTGRES, get_engine, session_scope
from app.database.models import (
    ActivityLog,
    AIUsage,
    ExportEvent,
    FeedbackTicket,
    LoginEvent,
    ScraperRun,
    TelemetryError,
    User,
)
from app.web.audit import log_event, quota_consumed_today
from app.web.deps import COOKIE_NAME, require_admin
from app.web.jobs import JOBS
from app.web.schemas import AdminPasswordReset, AdminUserUpdate, SettingsPatch
from app.web.security import create_access_token
from app.web.users import UserRepository

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(_: dict = Depends(require_admin)):
    user_stats = UserRepository.stats()
    try:
        from app.services.source_health import check_all
        health = check_all()
    except Exception as e:  # noqa: BLE001
        health = {"error": str(e)}
    try:
        from app.database.repositories import LeadRepository
        from app.database.extra_repositories import WatchRepository
        from app.database import SearchRepository
        leads = LeadRepository.stats()
        searches_count = len(SearchRepository.list_recent(1000))
        watches_count = len(WatchRepository.list_all(active_only=False))
    except Exception:
        leads, searches_count, watches_count = {}, 0, 0
    return {
        "users": user_stats,
        "health": health,
        "leads": leads,
        "searches_count": searches_count,
        "watches_count": watches_count,
        "db": {"backend": "postgres" if IS_POSTGRES else "sqlite",
               "url_safe": str(get_engine().url).split("@")[-1]},
        "jobs_running": sum(1 for j in JOBS.list_for() if j["status"] == "running"),
    }


# ---------- USUÁRIOS ----------
@router.get("/users")
def list_users(status: str | None = None, role: str | None = None,
               _: dict = Depends(require_admin)):
    return UserRepository.list_all(status=status, role=role)


@router.get("/users/{user_id}")
def get_user(user_id: int, _: dict = Depends(require_admin)):
    u = UserRepository.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return u


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, admin: dict = Depends(require_admin)):
    UserRepository.approve(user_id, admin["id"])
    return {"ok": True}


@router.post("/users/{user_id}/block")
def block_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Você não pode bloquear sua própria conta.")
    UserRepository.block(user_id)
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta.")
    UserRepository.reject(user_id)
    return {"ok": True}


@router.patch("/users/{user_id}")
def update_user(user_id: int, payload: AdminUserUpdate, admin: dict = Depends(require_admin)):
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    # Não permite o admin se rebaixar/desativar sozinho
    if user_id == admin["id"]:
        changes.pop("role", None)
        changes.pop("is_active", None)
        changes.pop("status", None)
    UserRepository.update(user_id, **changes)
    return {"ok": True}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, payload: AdminPasswordReset, _: dict = Depends(require_admin)):
    UserRepository.reset_password(user_id, payload.new_password)
    return {"ok": True}


# ---------- CONFIGURAÇÕES ----------
@router.get("/settings")
def get_app_settings(_: dict = Depends(require_admin)):
    s = get_settings()
    data = s.model_dump()
    # Mascara API keys ao expor
    for prov in ("deepseek", "openai"):
        key = data.get("ai", {}).get(prov, {}).get("api_key", "")
        if key:
            data["ai"][prov]["api_key_masked"] = key[:6] + "***" + key[-4:] if len(key) > 12 else "***"
    return data


@router.patch("/settings")
def patch_app_settings(patch: SettingsPatch, _: dict = Depends(require_admin)):
    current = get_settings().model_dump()
    incoming = {k: v for k, v in patch.model_dump().items() if v is not None}
    # merge raso por seção
    for section, values in incoming.items():
        if section in current and isinstance(current[section], dict):
            current[section].update(values)
        else:
            current[section] = values
    new_settings = Settings.model_validate(current)
    update_settings(new_settings)
    return {"ok": True}


# ---------- JOBS ----------
@router.get("/jobs")
def all_jobs(_: dict = Depends(require_admin)):
    return JOBS.list_for(user_id=None, limit=100)


@router.post("/jobs/cleanup")
def cleanup_jobs(_: dict = Depends(require_admin)):
    return {"removed": JOBS.cleanup()}


# =====================================================================
# ATIVIDADE / AUDIT LOG
# =====================================================================
def _activity_to_dict(a: ActivityLog) -> dict[str, Any]:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "user_email": a.user_email,
        "action": a.action,
        "summary": a.summary,
        "target_type": a.target_type,
        "target_id": a.target_id,
        "method": a.method,
        "path": a.path,
        "status_code": a.status_code,
        "duration_ms": a.duration_ms,
        "ip": a.ip,
        "user_agent": a.user_agent,
        "meta": a.meta,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/activity")
def list_activity(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    since_minutes: Optional[int] = None,
    q: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    _: dict = Depends(require_admin),
):
    with session_scope() as s:
        stmt = select(ActivityLog)
        if user_id:
            stmt = stmt.where(ActivityLog.user_id == user_id)
        if action:
            stmt = stmt.where(ActivityLog.action == action)
        if since_minutes:
            cutoff = datetime.utcnow() - timedelta(minutes=since_minutes)
            stmt = stmt.where(ActivityLog.created_at >= cutoff)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                (ActivityLog.user_email.ilike(like))
                | (ActivityLog.path.ilike(like))
                | (ActivityLog.summary.ilike(like))
            )
        stmt = stmt.order_by(desc(ActivityLog.created_at)).limit(limit).offset(offset)
        rows = [_activity_to_dict(a) for a in s.execute(stmt).scalars().all()]
    return {"items": rows, "count": len(rows)}


@router.get("/activity/online")
def online_users(_: dict = Depends(require_admin)):
    """Usuários ativos nos últimos 5 minutos (heartbeat por requests)."""
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    with session_scope() as s:
        stmt = select(User).where(User.last_seen_at >= cutoff).order_by(desc(User.last_seen_at))
        users = s.execute(stmt).scalars().all()
        rows = [{
            "id": u.id, "email": u.email, "full_name": u.full_name,
            "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
            "last_ip": getattr(u, "last_ip", "") or "",
        } for u in users]
    return {"online": rows, "count": len(rows)}


# =====================================================================
# DRILL-DOWN POR USUÁRIO
# =====================================================================
@router.get("/users/{user_id}/profile")
def user_profile(user_id: int, _: dict = Depends(require_admin)):
    u = UserRepository.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    with session_scope() as s:
        # ATIVIDADE recente
        acts = s.execute(
            select(ActivityLog).where(ActivityLog.user_id == user_id)
            .order_by(desc(ActivityLog.created_at)).limit(50)
        ).scalars().all()
        activity = [_activity_to_dict(a) for a in acts]

        # SCRAPER runs
        runs = s.execute(
            select(ScraperRun).where(ScraperRun.user_id == user_id)
            .order_by(desc(ScraperRun.created_at)).limit(50)
        ).scalars().all()
        scraper_runs = [{
            "id": r.id, "source": r.source, "query": r.query,
            "city": r.city, "state": r.state, "results": r.results,
            "duration_ms": r.duration_ms, "success": r.success, "blocked": r.blocked,
            "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in runs]

        # AI usage
        ai_rows = s.execute(
            select(AIUsage).where(AIUsage.user_id == user_id)
            .order_by(desc(AIUsage.created_at)).limit(50)
        ).scalars().all()
        ai = [{
            "id": a.id, "feature": a.feature, "provider": a.provider, "model": a.model,
            "prompt_tokens": a.prompt_tokens, "completion_tokens": a.completion_tokens,
            "total_tokens": a.total_tokens, "cost_usd": a.cost_usd,
            "latency_ms": a.latency_ms, "success": a.success, "error": a.error,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        } for a in ai_rows]

        # Exports
        exps = s.execute(
            select(ExportEvent).where(ExportEvent.user_id == user_id)
            .order_by(desc(ExportEvent.created_at)).limit(20)
        ).scalars().all()
        exports = [{
            "id": e.id, "format": e.format, "rows": e.rows,
            "filters": e.filters_json, "ip": e.ip,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        } for e in exps]

        # Logins
        logins = s.execute(
            select(LoginEvent).where(LoginEvent.user_id == user_id)
            .order_by(desc(LoginEvent.created_at)).limit(20)
        ).scalars().all()
        login_history = [{
            "success": ev.success, "reason": ev.reason, "ip": ev.ip,
            "user_agent": ev.user_agent,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        } for ev in logins]

        # Agregados
        ai_totals = s.execute(
            select(
                func.coalesce(func.sum(AIUsage.total_tokens), 0),
                func.coalesce(func.sum(AIUsage.cost_usd), 0.0),
                func.count(AIUsage.id),
            ).where(AIUsage.user_id == user_id)
        ).one()

    quota_today = quota_consumed_today(user_id, ["searches", "exports", "ai"])

    return {
        "user": u,
        "activity": activity,
        "scraper_runs": scraper_runs,
        "ai_usage": ai,
        "exports": exports,
        "login_history": login_history,
        "totals": {
            "ai_tokens": int(ai_totals[0] or 0),
            "ai_cost_usd": float(ai_totals[1] or 0.0),
            "ai_calls": int(ai_totals[2] or 0),
        },
        "quota_today": quota_today,
    }


# =====================================================================
# MÉTRICAS AGREGADAS
# =====================================================================
@router.get("/metrics")
def metrics(days: int = Query(default=14, ge=1, le=180), _: dict = Depends(require_admin)):
    cutoff = datetime.utcnow() - timedelta(days=days)
    with session_scope() as s:
        # Atividade por dia
        if IS_POSTGRES:
            day_expr = func.date_trunc("day", ActivityLog.created_at)
        else:
            day_expr = func.date(ActivityLog.created_at)
        per_day = s.execute(
            select(day_expr, func.count(ActivityLog.id))
            .where(ActivityLog.created_at >= cutoff)
            .group_by(day_expr).order_by(day_expr)
        ).all()
        per_day_out = [{"date": str(d), "count": int(n)} for d, n in per_day]

        # Top ações
        top_actions = s.execute(
            select(ActivityLog.action, func.count(ActivityLog.id))
            .where(ActivityLog.created_at >= cutoff)
            .group_by(ActivityLog.action)
            .order_by(desc(func.count(ActivityLog.id))).limit(15)
        ).all()

        # Top usuários por atividade
        top_users = s.execute(
            select(ActivityLog.user_email, func.count(ActivityLog.id))
            .where(and_(ActivityLog.created_at >= cutoff, ActivityLog.user_email != ""))
            .group_by(ActivityLog.user_email)
            .order_by(desc(func.count(ActivityLog.id))).limit(10)
        ).all()

        # Top buscas (queries)
        top_queries = s.execute(
            select(ScraperRun.query, func.count(ScraperRun.id))
            .where(and_(ScraperRun.created_at >= cutoff, ScraperRun.query != ""))
            .group_by(ScraperRun.query)
            .order_by(desc(func.count(ScraperRun.id))).limit(15)
        ).all()

        # Saúde scrapers (últimas 24h)
        cutoff_24 = datetime.utcnow() - timedelta(hours=24)
        sources = s.execute(
            select(
                ScraperRun.source,
                func.count(ScraperRun.id),
                func.sum(func.cast(ScraperRun.success, type_=ScraperRun.success.type)) if False else func.count(ScraperRun.id).label("c"),
            ).where(ScraperRun.created_at >= cutoff_24)
            .group_by(ScraperRun.source)
        ).all()
        # contagem fail manual
        scraper_health = []
        for src, total, _c in sources:
            fails = int(s.execute(
                select(func.count(ScraperRun.id)).where(
                    and_(ScraperRun.source == src,
                         ScraperRun.created_at >= cutoff_24,
                         ScraperRun.success == False)  # noqa: E712
                )
            ).scalar() or 0)
            blocked = int(s.execute(
                select(func.count(ScraperRun.id)).where(
                    and_(ScraperRun.source == src,
                         ScraperRun.created_at >= cutoff_24,
                         ScraperRun.blocked == True)  # noqa: E712
                )
            ).scalar() or 0)
            scraper_health.append({
                "source": src, "total": int(total),
                "failures": fails, "blocked": blocked,
                "success_rate": round((1 - fails / total) * 100, 1) if total else 100.0,
            })

        # AI cost / tokens
        ai_totals = s.execute(
            select(
                func.coalesce(func.sum(AIUsage.total_tokens), 0),
                func.coalesce(func.sum(AIUsage.cost_usd), 0.0),
                func.count(AIUsage.id),
            ).where(AIUsage.created_at >= cutoff)
        ).one()
        ai_top_users = s.execute(
            select(AIUsage.user_id, func.sum(AIUsage.cost_usd), func.sum(AIUsage.total_tokens))
            .where(AIUsage.created_at >= cutoff)
            .group_by(AIUsage.user_id)
            .order_by(desc(func.sum(AIUsage.cost_usd))).limit(10)
        ).all()

        # Heatmap (hora x dia da semana) — só funciona bem em postgres; fallback simples
        heatmap = []
        try:
            if IS_POSTGRES:
                rows = s.execute(
                    select(
                        func.extract("dow", ActivityLog.created_at).label("dow"),
                        func.extract("hour", ActivityLog.created_at).label("h"),
                        func.count(ActivityLog.id),
                    ).where(ActivityLog.created_at >= cutoff)
                    .group_by("dow", "h")
                ).all()
                heatmap = [{"dow": int(d), "hour": int(h), "count": int(n)} for d, h, n in rows]
        except Exception:
            heatmap = []

    return {
        "per_day": per_day_out,
        "top_actions": [{"action": a, "count": int(n)} for a, n in top_actions],
        "top_users": [{"email": e, "count": int(n)} for e, n in top_users],
        "top_queries": [{"query": q, "count": int(n)} for q, n in top_queries],
        "scraper_health": scraper_health,
        "ai": {
            "total_tokens": int(ai_totals[0] or 0),
            "total_cost_usd": float(ai_totals[1] or 0.0),
            "total_calls": int(ai_totals[2] or 0),
            "top_users": [
                {"user_id": uid, "cost_usd": float(c or 0), "tokens": int(t or 0)}
                for uid, c, t in ai_top_users
            ],
        },
        "heatmap": heatmap,
    }


# =====================================================================
# AI INSPECTOR
# =====================================================================
@router.get("/ai-usage")
def ai_usage(
    user_id: Optional[int] = None,
    feature: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    _: dict = Depends(require_admin),
):
    with session_scope() as s:
        stmt = select(AIUsage)
        if user_id:
            stmt = stmt.where(AIUsage.user_id == user_id)
        if feature:
            stmt = stmt.where(AIUsage.feature == feature)
        stmt = stmt.order_by(desc(AIUsage.created_at)).limit(limit)
        rows = s.execute(stmt).scalars().all()
        return [{
            "id": a.id, "user_id": a.user_id, "feature": a.feature,
            "provider": a.provider, "model": a.model,
            "prompt_tokens": a.prompt_tokens, "completion_tokens": a.completion_tokens,
            "total_tokens": a.total_tokens, "cost_usd": a.cost_usd,
            "latency_ms": a.latency_ms, "success": a.success, "error": a.error,
            "prompt_excerpt": a.prompt_excerpt, "response_excerpt": a.response_excerpt,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        } for a in rows]


# =====================================================================
# SCRAPER MONITOR
# =====================================================================
@router.get("/scraper-runs")
def scraper_runs(
    user_id: Optional[int] = None,
    source: Optional[str] = None,
    only_failed: bool = False,
    limit: int = Query(default=200, le=2000),
    _: dict = Depends(require_admin),
):
    with session_scope() as s:
        stmt = select(ScraperRun)
        if user_id:
            stmt = stmt.where(ScraperRun.user_id == user_id)
        if source:
            stmt = stmt.where(ScraperRun.source == source)
        if only_failed:
            stmt = stmt.where(ScraperRun.success == False)  # noqa: E712
        stmt = stmt.order_by(desc(ScraperRun.created_at)).limit(limit)
        rows = s.execute(stmt).scalars().all()
        return [{
            "id": r.id, "user_id": r.user_id, "source": r.source,
            "query": r.query, "city": r.city, "state": r.state,
            "results": r.results, "duration_ms": r.duration_ms,
            "success": r.success, "blocked": r.blocked, "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]


# =====================================================================
# EXPORTS AUDIT
# =====================================================================
@router.get("/exports")
def list_exports(limit: int = Query(default=200, le=2000), _: dict = Depends(require_admin)):
    with session_scope() as s:
        stmt = select(ExportEvent).order_by(desc(ExportEvent.created_at)).limit(limit)
        rows = s.execute(stmt).scalars().all()
        return [{
            "id": e.id, "user_id": e.user_id, "format": e.format,
            "rows": e.rows, "filters": e.filters_json, "ip": e.ip,
            "file_hash": e.file_hash,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        } for e in rows]


# =====================================================================
# LOGIN HISTORY
# =====================================================================
@router.get("/login-events")
def login_events(
    only_failed: bool = False,
    limit: int = Query(default=200, le=2000),
    _: dict = Depends(require_admin),
):
    with session_scope() as s:
        stmt = select(LoginEvent)
        if only_failed:
            stmt = stmt.where(LoginEvent.success == False)  # noqa: E712
        stmt = stmt.order_by(desc(LoginEvent.created_at)).limit(limit)
        rows = s.execute(stmt).scalars().all()
        return [{
            "id": ev.id, "user_id": ev.user_id, "email": ev.email,
            "success": ev.success, "reason": ev.reason,
            "ip": ev.ip, "user_agent": ev.user_agent,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        } for ev in rows]


# =====================================================================
# TELEMETRY ERRORS
# =====================================================================
@router.get("/errors")
def list_errors(limit: int = Query(default=200, le=2000), _: dict = Depends(require_admin)):
    with session_scope() as s:
        stmt = select(TelemetryError).order_by(desc(TelemetryError.created_at)).limit(limit)
        rows = s.execute(stmt).scalars().all()
        return [{
            "id": t.id, "user_id": t.user_id, "source": t.source,
            "page": t.page, "message": t.message, "stack": t.stack,
            "user_agent": t.user_agent, "meta": t.meta,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        } for t in rows]


# =====================================================================
# FEEDBACK / TICKETS
# =====================================================================
@router.get("/feedback")
def list_feedback(
    status: Optional[str] = None,
    limit: int = Query(default=200, le=1000),
    _: dict = Depends(require_admin),
):
    with session_scope() as s:
        stmt = select(FeedbackTicket)
        if status:
            stmt = stmt.where(FeedbackTicket.status == status)
        stmt = stmt.order_by(desc(FeedbackTicket.created_at)).limit(limit)
        rows = s.execute(stmt).scalars().all()
        return [{
            "id": f.id, "user_id": f.user_id, "user_email": f.user_email,
            "kind": f.kind, "subject": f.subject, "message": f.message,
            "page": f.page, "meta": f.meta, "status": f.status,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        } for f in rows]


@router.post("/feedback/{ticket_id}/close")
def close_ticket(ticket_id: int, _: dict = Depends(require_admin)):
    with session_scope() as s:
        t = s.get(FeedbackTicket, ticket_id)
        if not t:
            raise HTTPException(status_code=404, detail="Ticket não encontrado.")
        t.status = "closed"
    return {"ok": True}


# =====================================================================
# IMPERSONATE
# =====================================================================
@router.post("/users/{user_id}/impersonate")
def impersonate(user_id: int, response: Response, admin: dict = Depends(require_admin)):
    target = UserRepository.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if target["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="Você já é você mesmo.")
    token = create_access_token(
        sub=str(target["id"]),
        extra={
            "email": target["email"], "role": target["role"],
            "impersonated_by": admin["id"],
            "impersonator_email": admin["email"],
        },
    )
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax", secure=False,
        max_age=60 * 60 * 2, path="/",
    )
    log_event(
        user_id=admin["id"], user_email=admin["email"],
        action="impersonate",
        summary=f"Admin {admin['email']} entrou como {target['email']}",
        target_type="user", target_id=target["id"],
    )
    return {"ok": True, "user": target}
