"""Rotas de autenticação."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.web.deps import COOKIE_NAME, get_current_user_optional
from app.web.schemas import LoginIn, RegisterIn, TokenOut
from app.web.security import create_access_token, verify_password
from app.web.users import UserRepository

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, samesite="lax", secure=False,  # secure=True atrás de HTTPS
        max_age=60 * 60 * 24 * 7, path="/",
    )


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, response: Response):
    try:
        user = UserRepository.create(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            status="pending",  # exige aprovação do admin
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Não emitimos token até aprovação. Mas devolvemos o user pra UI.
    return {"access_token": "", "token_type": "bearer", "user": user}


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, response: Response):
    user = UserRepository.get_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=401, detail="Email ou senha inválidos.")
    pw_hash = UserRepository.get_password_hash(user["id"]) or ""
    if not verify_password(payload.password, pw_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos.")
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Conta desativada.")
    if user.get("status") == "pending":
        raise HTTPException(status_code=403, detail="Sua conta ainda aguarda aprovação do admin.")
    if user.get("status") == "blocked":
        raise HTTPException(status_code=403, detail="Conta bloqueada. Entre em contato com o admin.")
    UserRepository.touch_login(user["id"])
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
