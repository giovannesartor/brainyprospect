"""Hash de senha + JWT."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt  # PyJWT


# ----- senha (bcrypt direto, evita conflitos passlib<>bcrypt5) -----
def hash_password(plain: str) -> str:
    if not isinstance(plain, str):
        raise TypeError("password must be str")
    # bcrypt aceita até 72 bytes — truncamos antes para evitar erro.
    pw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed or not plain:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


# ----- JWT -----
def _secret() -> str:
    s = os.environ.get("SECRET_KEY", "").strip()
    if not s:
        # gera uma chave estável por processo (não use em produção sem SECRET_KEY!)
        s = "dev-insecure-" + hashlib.sha256(b"brainy-default").hexdigest()
    return s


JWT_ALG = "HS256"
JWT_DEFAULT_TTL_HOURS = 24 * 7  # 7 dias


def create_access_token(*, sub: str, extra: dict[str, Any] | None = None,
                         ttl_hours: int = JWT_DEFAULT_TTL_HOURS) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret(), algorithm=JWT_ALG)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, _secret(), algorithms=[JWT_ALG])
    except Exception:
        return None
