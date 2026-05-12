"""Rotas de autenticação."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.web.audit import log_event, log_login
from app.web.deps import COOKIE_NAME, get_current_user_optional
from app.web.schemas import LoginIn, RegisterIn, TokenOut
from app.web.security import create_access_token, verify_password
from app.web.users import UserRepository

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, samesite="lax", secure=False,  # secure=True atrás de HTTPS
        max_age=60 * 60 * 24 * 7, path="/",
    )


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, request: Request, response: Response):
    try:
        user = UserRepository.create(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            status="approved",  # auto-aprovação (beta fechado)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_event(
        user_id=user["id"], user_email=user["email"],
        action="register", summary=f"Novo cadastro: {user['email']}",
        target_type="user", target_id=user["id"],
    )
    token = create_access_token(sub=str(user["id"]),
                                extra={"email": user["email"], "role": user["role"]})
    _set_cookie(response, token)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, response: Response):
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    user = UserRepository.get_by_email(payload.email)
    if not user:
        log_login(email=payload.email, success=False, reason="email_not_found",
                  ip=ip, user_agent=ua)
        raise HTTPException(status_code=401, detail="Email ou senha inválidos.")
    pw_hash = UserRepository.get_password_hash(user["id"]) or ""
    if not verify_password(payload.password, pw_hash):
        log_login(email=payload.email, success=False, reason="bad_password",
                  user_id=user["id"], ip=ip, user_agent=ua)
        raise HTTPException(status_code=401, detail="Email ou senha inválidos.")
    if not user.get("is_active"):
        log_login(email=payload.email, success=False, reason="inactive",
                  user_id=user["id"], ip=ip, user_agent=ua)
        raise HTTPException(status_code=403, detail="Conta desativada.")
    if user.get("status") == "pending":
        log_login(email=payload.email, success=False, reason="pending",
                  user_id=user["id"], ip=ip, user_agent=ua)
        raise HTTPException(status_code=403, detail="Sua conta ainda aguarda aprovação do admin.")
    if user.get("status") == "blocked":
        log_login(email=payload.email, success=False, reason="blocked",
                  user_id=user["id"], ip=ip, user_agent=ua)
        raise HTTPException(status_code=403, detail="Conta bloqueada. Entre em contato com o admin.")
    UserRepository.touch_login(user["id"])
    log_login(email=user["email"], success=True, user_id=user["id"], ip=ip, user_agent=ua)
    token = create_access_token(sub=str(user["id"]),
                                extra={"email": user["email"], "role": user["role"]})
    _set_cookie(response, token)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    return user
