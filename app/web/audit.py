"""Audit log central — middleware FastAPI + helpers para registrar atividades.

Captura automaticamente requests relevantes (/api/...) e oferece API simples
para registrar eventos de domínio (login, IA, scraper, export, telemetria, etc).
"""
from __future__ import annotations

import json
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Iterable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.database.db import session_scope
from app.database.models import (
    ActivityLog,
    AIUsage,
    ExportEvent,
    LoginEvent,
    ScraperRun,
    TelemetryError,
    User,
)
from app.utils.logger import get_logger
from app.web.deps import COOKIE_NAME
from app.web.security import decode_token

log = get_logger("audit")

# Contexto de usuário ativo em jobs/threads (ex.: hunt em background).
_user_ctx: ContextVar[int | None] = ContextVar("audit_user_id", default=None)


def set_user_context(user_id: int | None) -> None:
    _user_ctx.set(user_id)


def current_user_id() -> int | None:
    return _user_ctx.get()

# Caminhos que NÃO devem ser auditados (ruído).
_SKIP_PATHS = (
    "/health",
    "/static/",
    "/favicon",
    "/manifest.webmanifest",
    "/sw.js",
    "/api/jobs/",          # polling
    "/api/admin/activity", # evita feedback loop
    "/api/admin/overview", # polling
    "/api/auth/me",        # polling
)

# Métodos por path → ação semântica (resumo amigável)
_ACTION_HINTS = {
    ("POST", "/api/hunt"):              ("hunt_start", "Iniciou prospecção"),
    ("POST", "/api/hunt-lookalike"):    ("lookalike_start", "Iniciou hunt lookalike"),
    ("POST", "/api/analyze"):           ("analyze", "Analisou empresa"),
    ("GET",  "/api/leads/export"):      ("export", "Exportou leads"),
    ("POST", "/api/objections"):        ("ai_objection", "Gerou resposta de objeção"),
    ("POST", "/api/chat"):              ("ai_chat", "Conversou com Brainy Chat"),
    ("POST", "/api/auth/login"):        ("login_attempt", "Tentou login"),
    ("POST", "/api/auth/register"):     ("register", "Cadastro"),
    ("POST", "/api/auth/logout"):       ("logout", "Saiu"),
    ("DELETE", "/api/leads"):           ("lead_delete", "Excluiu lead"),
    ("PATCH",  "/api/leads"):           ("lead_update", "Atualizou lead"),
}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def _decode_user(request: Request) -> tuple[int | None, str]:
    tok = request.headers.get("authorization", "")
    if tok.lower().startswith("bearer "):
        tok = tok[7:].strip()
    else:
        tok = request.cookies.get(COOKIE_NAME, "")
    if not tok:
        return None, ""
    payload = decode_token(tok) or {}
    sub = payload.get("sub")
    try:
        uid = int(sub) if sub is not None else None
    except (TypeError, ValueError):
        uid = None
    return uid, str(payload.get("email") or "")


def _classify(method: str, path: str) -> tuple[str, str]:
    # match por prefixo
    for (m, p), (action, summary) in _ACTION_HINTS.items():
        if m == method and path.startswith(p):
            return action, summary
    # genérico
    return f"{method.lower()}_{path.strip('/').replace('/', '_')[:40]}", ""


def _should_skip(path: str) -> bool:
    if not path.startswith("/api/"):
        return True
    return any(path.startswith(s) for s in _SKIP_PATHS)


class AuditMiddleware(BaseHTTPMiddleware):
    """Loga cada chamada relevante a /api/* na tabela activity_log."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        path = request.url.path
        method = request.method
        skip = _should_skip(path)

        response = None
        status_code = 0
        err: Exception | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            err = e
            status_code = 500
            raise
        finally:
            try:
                if not skip:
                    duration = int((time.perf_counter() - start) * 1000)
                    uid, email = _decode_user(request)
                    action, summary = _classify(method, path)
                    ip = _client_ip(request)
                    ua = request.headers.get("user-agent", "")[:255]
                    _persist_request(
                        user_id=uid,
                        user_email=email,
                        action=action,
                        method=method,
                        path=path,
                        status_code=status_code,
                        duration_ms=duration,
                        ip=ip,
                        user_agent=ua,
                        summary=summary,
                        meta={"qs": dict(request.query_params)} if request.query_params else None,
                        error=str(err) if err else "",
                    )
                    if uid:
                        _touch_user(uid, ip, ua)
            except Exception as ex:  # nunca derruba a request
                log.warning(f"audit middleware falhou: {ex}")
        return response


def _persist_request(**fields: Any) -> None:
    err = fields.pop("error", "")
    meta = fields.get("meta") or {}
    if err:
        meta = {**meta, "error": err[:500]}
    fields["meta"] = meta or None
    try:
        with session_scope() as s:
            s.add(ActivityLog(**fields))
    except Exception as e:  # noqa: BLE001
        log.debug(f"persist activity falhou: {e}")


def _touch_user(uid: int, ip: str, ua: str) -> None:
    try:
        with session_scope() as s:
            u = s.get(User, uid)
            if not u:
                return
            u.last_seen_at = datetime.utcnow()
            if ip:
                u.last_ip = ip[:64]
            if ua:
                u.last_user_agent = ua[:255]
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers de domínio (chamados explicitamente pelas rotas/serviços)
# ---------------------------------------------------------------------------
def log_event(
    *,
    user_id: int | None,
    action: str,
    summary: str = "",
    target_type: str = "",
    target_id: str | int = "",
    meta: dict | None = None,
    user_email: str = "",
) -> None:
    """Registra uma atividade de domínio (não vinculada a uma request)."""
    try:
        with session_scope() as s:
            s.add(ActivityLog(
                user_id=user_id,
                user_email=user_email or "",
                action=action,
                summary=summary[:500],
                target_type=target_type,
                target_id=str(target_id),
                meta=meta,
            ))
    except Exception as e:  # noqa: BLE001
        log.debug(f"log_event falhou: {e}")


def log_login(*, email: str, success: bool, reason: str = "",
              user_id: int | None = None, ip: str = "", user_agent: str = "") -> None:
    try:
        with session_scope() as s:
            s.add(LoginEvent(
                user_id=user_id, email=email or "", success=success,
                reason=reason[:120], ip=ip[:64], user_agent=(user_agent or "")[:255],
            ))
    except Exception:
        pass


def log_ai_usage(
    *,
    user_id: int | None,
    provider: str,
    model: str,
    feature: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
    success: bool = True,
    error: str = "",
    prompt_excerpt: str = "",
    response_excerpt: str = "",
) -> None:
    try:
        with session_scope() as s:
            s.add(AIUsage(
                user_id=user_id, provider=provider or "", model=model or "",
                feature=feature or "", prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=(prompt_tokens or 0) + (completion_tokens or 0),
                cost_usd=cost_usd, latency_ms=latency_ms,
                success=success, error=error[:500],
                prompt_excerpt=(prompt_excerpt or "")[:1500],
                response_excerpt=(response_excerpt or "")[:1500],
            ))
    except Exception as e:  # noqa: BLE001
        log.debug(f"log_ai_usage falhou: {e}")


def log_scraper_run(
    *,
    user_id: int | None,
    source: str,
    query: str = "",
    city: str = "",
    state: str = "",
    results: int = 0,
    duration_ms: int = 0,
    success: bool = True,
    error: str = "",
    blocked: bool = False,
) -> None:
    try:
        with session_scope() as s:
            s.add(ScraperRun(
                user_id=user_id, source=source, query=(query or "")[:500],
                city=city or "", state=state or "", results=results,
                duration_ms=duration_ms, success=success, error=error[:500],
                blocked=blocked,
            ))
    except Exception:
        pass


def log_export(
    *,
    user_id: int | None,
    fmt: str,
    rows: int,
    filters: dict | None = None,
    file_hash: str = "",
    ip: str = "",
) -> None:
    try:
        with session_scope() as s:
            s.add(ExportEvent(
                user_id=user_id, format=fmt, rows=rows,
                filters_json=filters, file_hash=file_hash, ip=ip[:64],
            ))
    except Exception:
        pass


def log_telemetry_error(
    *,
    user_id: int | None,
    source: str,
    page: str,
    message: str,
    stack: str = "",
    user_agent: str = "",
    meta: dict | None = None,
) -> None:
    try:
        with session_scope() as s:
            s.add(TelemetryError(
                user_id=user_id, source=source[:20], page=(page or "")[:255],
                message=(message or "")[:2000], stack=(stack or "")[:5000],
                user_agent=(user_agent or "")[:255], meta=meta,
            ))
    except Exception:
        pass


def quota_consumed_today(user_id: int, kinds: Iterable[str]) -> dict[str, int]:
    """Retorna consumo diário do usuário por tipo: searches/exports/ai."""
    from sqlalchemy import func, select, and_
    from datetime import date, time as dtime
    today_start = datetime.combine(date.today(), dtime.min)
    out = {k: 0 for k in kinds}
    try:
        with session_scope() as s:
            if "searches" in out:
                out["searches"] = int(s.execute(
                    select(func.count(ScraperRun.id)).where(
                        and_(ScraperRun.user_id == user_id, ScraperRun.created_at >= today_start)
                    )
                ).scalar() or 0)
            if "exports" in out:
                out["exports"] = int(s.execute(
                    select(func.count(ExportEvent.id)).where(
                        and_(ExportEvent.user_id == user_id, ExportEvent.created_at >= today_start)
                    )
                ).scalar() or 0)
            if "ai" in out:
                out["ai"] = int(s.execute(
                    select(func.count(AIUsage.id)).where(
                        and_(AIUsage.user_id == user_id, AIUsage.created_at >= today_start)
                    )
                ).scalar() or 0)
    except Exception:
        pass
    return out
