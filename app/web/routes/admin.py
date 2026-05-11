"""Painel admin: usuários, configurações globais, saúde, logs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config.settings_manager import (
    Settings,
    get_settings,
    update_settings,
)
from app.database.db import IS_POSTGRES, get_engine
from app.web.deps import require_admin
from app.web.jobs import JOBS
from app.web.schemas import AdminPasswordReset, AdminUserUpdate, SettingsPatch
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
