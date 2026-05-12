"""Repositório de usuários."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select

from app.database.db import session_scope
from app.database.models import User
from app.web.security import hash_password


def _to_dict(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "status": u.status,
        "is_active": bool(u.is_active),
        "created_at": u.created_at,
        "last_login_at": u.last_login_at,
        "last_seen_at": getattr(u, "last_seen_at", None),
        "last_ip": getattr(u, "last_ip", "") or "",
        "last_user_agent": getattr(u, "last_user_agent", "") or "",
        "approved_at": u.approved_at,
        "approved_by": u.approved_by,
        "notes": u.notes,
        "quota_searches_per_day": getattr(u, "quota_searches_per_day", None),
        "quota_exports_per_day": getattr(u, "quota_exports_per_day", None),
        "quota_ai_per_day": getattr(u, "quota_ai_per_day", None),
    }


class UserRepository:
    @staticmethod
    def get_by_email(email: str) -> dict[str, Any] | None:
        email = (email or "").strip().lower()
        if not email:
            return None
        with session_scope() as s:
            obj = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
            return _to_dict(obj) if obj else None

    @staticmethod
    def get(user_id: int) -> dict[str, Any] | None:
        with session_scope() as s:
            obj = s.get(User, user_id)
            return _to_dict(obj) if obj else None

    @staticmethod
    def get_password_hash(user_id: int) -> str | None:
        with session_scope() as s:
            obj = s.get(User, user_id)
            return obj.password_hash if obj else None

    @staticmethod
    def create(*, email: str, password: str, full_name: str = "",
               role: str = "user", status: str = "pending") -> dict[str, Any]:
        email = email.strip().lower()
        with session_scope() as s:
            existing = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing:
                raise ValueError("Email já cadastrado.")
            obj = User(
                email=email,
                full_name=full_name.strip(),
                password_hash=hash_password(password),
                role=role,
                status=status,
                approved_at=datetime.utcnow() if status == "approved" else None,
            )
            s.add(obj)
            s.flush()
            return _to_dict(obj)

    @staticmethod
    def ensure_admin(*, email: str, password: str, full_name: str = "Admin") -> dict[str, Any]:
        """Cria (ou promove) admin garantido. Idempotente."""
        email = email.strip().lower()
        with session_scope() as s:
            obj = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if obj is None:
                obj = User(
                    email=email,
                    full_name=full_name,
                    password_hash=hash_password(password),
                    role="admin",
                    status="approved",
                    is_active=True,
                    approved_at=datetime.utcnow(),
                )
                s.add(obj)
                s.flush()
            else:
                obj.role = "admin"
                obj.status = "approved"
                obj.is_active = True
                if obj.approved_at is None:
                    obj.approved_at = datetime.utcnow()
                # Não sobrescreve a senha em re-deploys, exceto se BRAINY_ADMIN_RESET_PASSWORD=1
                import os
                if os.environ.get("BRAINY_ADMIN_RESET_PASSWORD") == "1":
                    obj.password_hash = hash_password(password)
            return _to_dict(obj)

    @staticmethod
    def list_all(*, status: str | None = None, role: str | None = None,
                 limit: int = 500) -> list[dict[str, Any]]:
        with session_scope() as s:
            stmt = select(User)
            if status:
                stmt = stmt.where(User.status == status)
            if role:
                stmt = stmt.where(User.role == role)
            stmt = stmt.order_by(desc(User.created_at)).limit(limit)
            return [_to_dict(u) for u in s.execute(stmt).scalars().all()]

    @staticmethod
    def update(user_id: int, **changes) -> None:
        with session_scope() as s:
            obj = s.get(User, user_id)
            if not obj:
                return
            allowed = {"full_name", "role", "status", "is_active", "notes",
                       "quota_searches_per_day", "quota_exports_per_day", "quota_ai_per_day"}
            for k, v in changes.items():
                if k in allowed:
                    setattr(obj, k, v)

    @staticmethod
    def approve(user_id: int, approver_id: int) -> None:
        with session_scope() as s:
            obj = s.get(User, user_id)
            if not obj:
                return
            obj.status = "approved"
            obj.is_active = True
            obj.approved_at = datetime.utcnow()
            obj.approved_by = approver_id

    @staticmethod
    def block(user_id: int) -> None:
        with session_scope() as s:
            obj = s.get(User, user_id)
            if obj:
                obj.status = "blocked"
                obj.is_active = False

    @staticmethod
    def reject(user_id: int) -> None:
        with session_scope() as s:
            obj = s.get(User, user_id)
            if obj:
                s.delete(obj)

    @staticmethod
    def reset_password(user_id: int, new_password: str) -> None:
        with session_scope() as s:
            obj = s.get(User, user_id)
            if obj:
                obj.password_hash = hash_password(new_password)

    @staticmethod
    def touch_login(user_id: int) -> None:
        with session_scope() as s:
            obj = s.get(User, user_id)
            if obj:
                obj.last_login_at = datetime.utcnow()

    @staticmethod
    def stats() -> dict[str, int]:
        with session_scope() as s:
            return {
                "total": int(s.execute(select(func.count(User.id))).scalar_one() or 0),
                "approved": int(s.execute(
                    select(func.count(User.id)).where(User.status == "approved")
                ).scalar_one() or 0),
                "pending": int(s.execute(
                    select(func.count(User.id)).where(User.status == "pending")
                ).scalar_one() or 0),
                "blocked": int(s.execute(
                    select(func.count(User.id)).where(User.status == "blocked")
                ).scalar_one() or 0),
                "admins": int(s.execute(
                    select(func.count(User.id)).where(User.role == "admin")
                ).scalar_one() or 0),
            }
