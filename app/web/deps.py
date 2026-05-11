"""Dependências FastAPI: usuário logado, admin etc."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status

from app.web.security import decode_token
from app.web.users import UserRepository


COOKIE_NAME = "bp_token"


def _extract_token(request: Request) -> str | None:
    # 1) Authorization: Bearer xxx
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # 2) Cookie
    tok = request.cookies.get(COOKIE_NAME)
    if tok:
        return tok
    return None


def get_current_user_optional(request: Request) -> Optional[dict[str, Any]]:
    tok = _extract_token(request)
    if not tok:
        return None
    payload = decode_token(tok)
    if not payload:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        uid = int(sub)
    except (TypeError, ValueError):
        return None
    user = UserRepository.get(uid)
    if not user or not user.get("is_active") or user.get("status") != "approved":
        return None
    return user


def require_user(request: Request) -> dict[str, Any]:
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a admins.")
    return user
