"""Endpoints públicos: telemetria de erros e feedback dos usuários."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.database.db import session_scope
from app.database.models import FeedbackTicket
from app.web.audit import log_telemetry_error
from app.web.deps import get_current_user_optional

router = APIRouter(prefix="/api", tags=["telemetry"])


class TelemetryErrorIn(BaseModel):
    message: str = Field(max_length=2000)
    stack: str = Field(default="", max_length=5000)
    page: str = Field(default="", max_length=255)
    meta: Optional[dict] = None


@router.post("/telemetry/error")
def report_error(payload: TelemetryErrorIn, request: Request):
    user = get_current_user_optional(request)
    log_telemetry_error(
        user_id=user["id"] if user else None,
        source="frontend",
        page=payload.page,
        message=payload.message,
        stack=payload.stack,
        user_agent=request.headers.get("user-agent", ""),
        meta=payload.meta,
    )
    return {"ok": True}


class FeedbackIn(BaseModel):
    kind: str = Field(default="feedback", max_length=40)  # bug/feedback/idea
    subject: str = Field(default="", max_length=255)
    message: str = Field(max_length=5000)
    page: str = Field(default="", max_length=255)
    meta: Optional[dict] = None


@router.post("/feedback")
def send_feedback(payload: FeedbackIn, request: Request):
    user = get_current_user_optional(request)
    with session_scope() as s:
        s.add(FeedbackTicket(
            user_id=user["id"] if user else None,
            user_email=user["email"] if user else "",
            kind=payload.kind, subject=payload.subject[:255],
            message=payload.message, page=payload.page,
            meta=payload.meta, status="open",
        ))
    return {"ok": True}
