"""Modelos de domínio Pydantic compartilhados."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


PROSPECTION_MODES = ("direct_sale", "partners")


class ICPProfile(BaseModel):
    business_type: str = ""
    summary: str = ""
    ideal_clients: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    commercial_score: int = 0
    # Sugestão estratégica
    recommended_mode: str = ""            # 'direct_sale' | 'partners'
    recommended_reason: str = ""
    # Listas específicas por modo
    direct_clients: list[str] = Field(default_factory=list)
    direct_keywords: list[str] = Field(default_factory=list)
    partner_segments: list[str] = Field(default_factory=list)
    partner_keywords: list[str] = Field(default_factory=list)
    # Produtos/serviços detectados no site (cada um com seus próprios públicos)
    # Schema de cada item:
    # {
    #   "name": str, "description": str, "recommended_mode": str,
    #   "direct_clients": [str], "direct_keywords": [str],
    #   "partner_segments": [str], "partner_keywords": [str]
    # }
    products: list[dict] = Field(default_factory=list)


class LeadDraft(BaseModel):
    """Lead em construção, antes de persistir."""
    name: str = ""
    niche: str = ""
    city: str = ""
    state: str = ""
    country: str = "Brasil"
    address: str = ""
    website: str = ""
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    instagram: str = ""
    linkedin: str = ""
    google_rating: float | None = None
    google_reviews: int | None = None
    score: int = 0
    score_reason: str = ""
    pitch: str = ""
    status: str = "novo"
    prospection_mode: str = "direct_sale"
    tags: str = ""

    # Enriquecimento avançado
    cnpj: str = ""
    company_size: str = ""
    employees_estimate: int | None = None
    years_in_market: int | None = None
    technologies: str = ""
    decision_makers: list[dict] | None = None
    buying_signals: list[str] | None = None

    # Inteligência comercial
    match_score: int = 0
    priority: str = "media"
    why_matters: str = ""
    opportunity_when: str = ""
    opportunity_channel: str = ""
    opportunity_offer: str = ""
    ticket_estimate: str = ""
    revenue_year_estimate: str = ""

    # CRM
    observations: str = ""
    follow_up_text: str = ""
    last_contact_at: datetime | None = None
    next_followup_at: datetime | None = None
    campaign_id: int | None = None

    # Mensagens prontas + status de envio
    message_a: str = ""
    message_b: str = ""
    message_opener: str = ""
    message_tone: str = ""
    send_status: str = "nao_enviado"
    hot_score: int = 0
    followup_step: int = 0

    extra: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_db(self) -> dict[str, Any]:
        d = self.model_dump()
        d.pop("created_at", None)
        return d


class QualificationResult(BaseModel):
    score: int = 0
    reason: str = ""
    pitch: str = ""
    match_score: int = 0
    why_matters: str = ""
    opportunity_when: str = ""
    opportunity_channel: str = ""
    opportunity_offer: str = ""
    ticket_estimate: str = ""
    revenue_year_estimate: str = ""
    follow_up_text: str = ""
    tags: list[str] = Field(default_factory=list)
