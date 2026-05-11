"""Programador de follow-ups (D1).

Função pura — calcula quem está vencido e renderiza próxima mensagem.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import get_settings
from app.database import LeadRepository
from app.services.messaging import render_template


def compute_due_followups(now: datetime | None = None) -> list[dict[str, Any]]:
    """Retorna leads com follow-up vencido (next_followup_at <= agora)."""
    return LeadRepository.due_followups(now=now)


def next_followup_text(lead: dict) -> tuple[str, int]:
    """Renderiza o próximo follow-up para esse lead.

    Retorna (mensagem, novo_step). Se já passou do step 3, retorna ("", step).
    """
    s = get_settings()
    step = int(lead.get("followup_step") or 0)
    templates = [s.messages.followup_1, s.messages.followup_2, s.messages.followup_3]
    if step >= 3:
        return "", step
    template = templates[step] or ""
    msg = render_template(template, lead, opener=lead.get("message_opener") or "")
    return msg, step + 1


def advance_and_schedule(lead_id: int) -> str:
    """Marca follow-up enviado e agenda o próximo (se houver).

    Retorna a mensagem renderizada que deve ser enviada agora.
    """
    s = get_settings()
    lead = LeadRepository.get(lead_id)
    if not lead:
        return ""
    msg, new_step = next_followup_text(lead)
    if not msg:
        return ""
    LeadRepository.advance_followup_step(lead_id)
    days = s.messages.followup_days
    if new_step < len(days):
        LeadRepository.schedule_next_followup(lead_id, days[new_step])
    return msg
