"""Perfil ICP do usuário (seu próprio negócio) — armazenado em JSON local.

Usado pela IA para:
- recomputar match_score quando ICP mudar
- gerar respostas a objeções com contexto
- onboarding inicial
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.paths import USER_DIR


_PATH: Path = USER_DIR / "user_icp.json"


def load() -> dict[str, Any]:
    if not _PATH.exists():
        return {}
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save(data: dict[str, Any]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_configured() -> bool:
    d = load()
    return bool(d.get("business_summary") or d.get("website"))


def summary_for_ai() -> str:
    d = load()
    if not d:
        return ""
    parts = [
        f"Empresa: {d.get('company_name','')}",
        f"Site: {d.get('website','')}",
        f"O que vendemos: {d.get('business_summary','')}",
        f"Cliente ideal: {d.get('ideal_client','')}",
        f"Ticket médio: {d.get('avg_ticket','')}",
        f"Diferenciais: {d.get('differentials','')}",
    ]
    return "\n".join(p for p in parts if p.split(":", 1)[1].strip())
