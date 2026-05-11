"""Helpers utilitários: links de contato, validações."""
from __future__ import annotations

import re
from urllib.parse import quote


def normalize_phone(raw: str) -> str:
    """Remove tudo que não é dígito e adiciona 55 se for telefone BR sem DDI."""
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return ""
    # 11 dígitos = celular BR sem DDI
    if len(digits) in (10, 11):
        digits = "55" + digits
    return digits


def whatsapp_link(phone: str, message: str = "") -> str:
    p = normalize_phone(phone)
    if not p:
        return ""
    base = f"https://wa.me/{p}"
    if message:
        return f"{base}?text={quote(message)}"
    return base


def mailto_link(email: str, subject: str = "", body: str = "") -> str:
    if not email:
        return ""
    parts = []
    if subject:
        parts.append(f"subject={quote(subject)}")
    if body:
        parts.append(f"body={quote(body)}")
    qs = ("?" + "&".join(parts)) if parts else ""
    return f"mailto:{email}{qs}"


def best_contact_phone(lead: dict) -> str:
    """Retorna whatsapp se existir, senão phone."""
    return (lead.get("whatsapp") or lead.get("phone") or "").strip()
