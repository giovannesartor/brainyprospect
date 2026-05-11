"""Exportação de leads para CSV / XLSX / JSON."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from app.database import ExportRepository
from app.paths import EXPORTS_DIR

COLUMNS = [
    "id", "name", "prospection_mode", "lead_type", "priority", "tags",
    "niche", "city", "state", "country", "address",
    "website", "phone", "whatsapp", "email", "instagram", "linkedin",
    "google_rating", "google_reviews",
    "cnpj", "company_size", "employees_estimate", "years_in_market",
    "technologies", "buying_signals", "decision_makers",
    "score", "match_score", "score_reason",
    "why_matters", "opportunity_when", "opportunity_channel",
    "opportunity_offer", "ticket_estimate", "revenue_year_estimate",
    "pitch", "follow_up_text", "observations",
    "status", "campaign_id", "last_contact_at", "next_followup_at", "created_at",
]

MODE_LABEL = {"direct_sale": "Venda Direta", "partners": "Parceiro"}


def _stringify_complex(v):
    if v is None:
        return ""
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            return "; ".join(f"{d.get('name','')} ({d.get('role','')})" for d in v)
        return ", ".join(str(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return v


def _normalize(rows: Iterable[dict]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)
    if "prospection_mode" not in df.columns:
        df["prospection_mode"] = ""
    df["lead_type"] = df["prospection_mode"].map(lambda v: MODE_LABEL.get(str(v or ""), "—"))
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    # serializa colunas complexas
    for col in ("buying_signals", "decision_makers"):
        if col in df.columns:
            df[col] = df[col].map(_stringify_complex)
    return df[COLUMNS]


def _filename(prefix: str, ext: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return EXPORTS_DIR / f"{prefix}_{ts}.{ext}"


def export_csv(rows: Iterable[dict], prefix: str = "leads") -> Path:
    df = _normalize(rows)
    path = _filename(prefix, "csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    ExportRepository.register(str(path), "csv", len(df))
    return path


def export_xlsx(rows: Iterable[dict], prefix: str = "leads") -> Path:
    df = _normalize(rows)
    path = _filename(prefix, "xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Leads", index=False)
        ws = writer.sheets["Leads"]
        # auto-largura simples
        for column_cells in ws.columns:
            max_len = max(
                (len(str(c.value)) for c in column_cells if c.value is not None),
                default=10,
            )
            ws.column_dimensions[column_cells[0].column_letter].width = min(max_len + 2, 60)
    ExportRepository.register(str(path), "xlsx", len(df))
    return path


def export_json(rows: Iterable[dict], prefix: str = "leads") -> Path:
    df = _normalize(rows)
    path = _filename(prefix, "json")
    payload = json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ExportRepository.register(str(path), "json", len(df))
    return path
