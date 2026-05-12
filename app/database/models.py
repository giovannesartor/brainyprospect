"""Modelos ORM."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


class Search(Base):
    """Histórico de pesquisas executadas."""
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_input: Mapped[str] = mapped_column(String(500))
    niche: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(120), default="Brasil")
    business_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    icp_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prospection_mode: Mapped[str] = mapped_column(String(20), default="direct_sale", index=True)
    recommended_mode: Mapped[str] = mapped_column(String(20), default="")
    total_leads: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    leads: Mapped[list["Lead"]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
    )


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("name", "city", "phone", name="uq_lead_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int | None] = mapped_column(
        ForeignKey("searches.id", ondelete="CASCADE"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    niche: Mapped[str] = mapped_column(String(200), default="", index=True)
    city: Mapped[str] = mapped_column(String(120), default="", index=True)
    state: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(120), default="Brasil")
    address: Mapped[str] = mapped_column(String(500), default="")

    website: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str] = mapped_column(String(50), default="", index=True)
    whatsapp: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(255), default="", index=True)
    instagram: Mapped[str] = mapped_column(String(255), default="")
    linkedin: Mapped[str] = mapped_column(String(255), default="")

    google_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    google_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)

    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    score_reason: Mapped[str] = mapped_column(Text, default="")
    pitch: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="novo", index=True)
    prospection_mode: Mapped[str] = mapped_column(String(20), default="direct_sale", index=True)
    tags: Mapped[str] = mapped_column(String(500), default="")

    # Enriquecimento avançado
    cnpj: Mapped[str] = mapped_column(String(20), default="")
    company_size: Mapped[str] = mapped_column(String(40), default="")  # MEI/Pequena/Média/Grande
    employees_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    years_in_market: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technologies: Mapped[str] = mapped_column(String(500), default="")  # csv
    decision_makers: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # [{name, role}]
    buying_signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # [str]

    # Inteligência comercial
    match_score: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    priority: Mapped[str] = mapped_column(String(20), default="media", index=True)  # maxima/alta/media/baixa
    why_matters: Mapped[str] = mapped_column(Text, default="")
    opportunity_when: Mapped[str] = mapped_column(String(120), default="")
    opportunity_channel: Mapped[str] = mapped_column(String(40), default="")
    opportunity_offer: Mapped[str] = mapped_column(Text, default="")
    ticket_estimate: Mapped[str] = mapped_column(String(60), default="")
    revenue_year_estimate: Mapped[str] = mapped_column(String(60), default="")

    # CRM
    observations: Mapped[str] = mapped_column(Text, default="")
    follow_up_text: Mapped[str] = mapped_column(Text, default="")
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Mensagens prontas (template renderizado pelo app + abertura IA personalizada)
    message_a: Mapped[str] = mapped_column(Text, default="")
    message_b: Mapped[str] = mapped_column(Text, default="")
    message_opener: Mapped[str] = mapped_column(String(500), default="")
    message_tone: Mapped[str] = mapped_column(String(20), default="")  # formal/casual
    send_status: Mapped[str] = mapped_column(String(30), default="nao_enviado", index=True)
    # Score de "quente" (0-100) calculado a partir de site, contatos, sinais
    hot_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    followup_step: Mapped[int] = mapped_column(Integer, default=0)  # 0=nenhum, 1/2/3

    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    search: Mapped[Search | None] = relationship(back_populates="leads")
    campaign: Mapped["Campaign | None"] = relationship(back_populates="leads")


class Campaign(Base):
    """Agrupamento comercial: ex. 'Contabilidades RS', 'Holdings Premium'."""
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    target_mode: Mapped[str] = mapped_column(String(20), default="direct_sale")
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    leads: Mapped[list["Lead"]] = relationship(back_populates="campaign")


class LogEntry(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str] = mapped_column(String(80), default="app")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ExportRecord(Base):
    __tablename__ = "exports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_path: Mapped[str] = mapped_column(String(500))
    format: Mapped[str] = mapped_column(String(10))
    rows: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WatchItem(Base):
    """Empresa adicionada à watch-list para re-scrape periódico."""
    __tablename__ = "watch_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    website: Mapped[str] = mapped_column(String(500), index=True)
    last_hash: Mapped[str] = mapped_column(String(64), default="")
    last_title: Mapped[str] = mapped_column(String(255), default="")
    last_text_excerpt: Mapped[str] = mapped_column(Text, default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=7)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WatchEvent(Base):
    """Registro de mudança detectada em uma WatchItem."""
    __tablename__ = "watch_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[int] = mapped_column(
        ForeignKey("watch_items.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))     # site_changed, title_changed, new_signal
    summary: Mapped[str] = mapped_column(Text, default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Objection(Base):
    """Objeção comercial registrada com respostas geradas pela IA."""
    __tablename__ = "objections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objection_text: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")
    responses_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class LeadInteraction(Base):
    """Histórico de interações com um lead (envios, respostas, notas)."""
    __tablename__ = "lead_interactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), index=True)
    # whatsapp_sent / email_sent / note / status_change / followup_sent / replied
    channel: Mapped[str] = mapped_column(String(30), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AnalysisCache(Base):
    """Cache de análises de site/descrição feitas pela IA.

    Chave: hash do input normalizado. TTL configurável (default 7 dias).
    """
    __tablename__ = "analysis_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_input: Mapped[str] = mapped_column(String(500))
    is_website: Mapped[bool] = mapped_column(Boolean, default=False)
    icp_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    business_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    hits: Mapped[int] = mapped_column(Integer, default=0)


# ----------------------------------------------------------------------
# WEB AUTH — usuários, papéis e aprovação por admin
# ----------------------------------------------------------------------
class User(Base):
    """Usuário da plataforma web."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)  # user | admin
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending | approved | blocked
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_ip: Mapped[str] = mapped_column(String(64), default="")
    last_user_agent: Mapped[str] = mapped_column(String(255), default="")
    # Cotas (override por usuário)
    quota_searches_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_exports_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_ai_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ----------------------------------------------------------------------
# AUDIT LOG / ATIVIDADE / SEGURANÇA / IA
# ----------------------------------------------------------------------
class ActivityLog(Base):
    """Registro centralizado de ações dos usuários (audit log)."""
    __tablename__ = "activity_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_email: Mapped[str] = mapped_column(String(255), default="", index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(40), default="", index=True)
    target_id: Mapped[str] = mapped_column(String(80), default="")
    method: Mapped[str] = mapped_column(String(10), default="")
    path: Mapped[str] = mapped_column(String(500), default="")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class LoginEvent(Base):
    """Histórico de tentativas de login."""
    __tablename__ = "login_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), default="", index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reason: Mapped[str] = mapped_column(String(120), default="")
    ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AIUsage(Base):
    """Cada chamada à IA — tokens, custo, latência, contexto."""
    __tablename__ = "ai_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="", index=True)
    model: Mapped[str] = mapped_column(String(80), default="")
    feature: Mapped[str] = mapped_column(String(80), default="", index=True)  # chat/qualify/objection/...
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str] = mapped_column(String(500), default="")
    prompt_excerpt: Mapped[str] = mapped_column(Text, default="")
    response_excerpt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ScraperRun(Base):
    """Cada execução de scraper (busca individual)."""
    __tablename__ = "scraper_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(40), default="", index=True)  # google_maps/bing/ddg/site
    query: Mapped[str] = mapped_column(String(500), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    results: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    error: Mapped[str] = mapped_column(String(500), default="")
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # CAPTCHA/429
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ExportEvent(Base):
    """Auditoria de exports (CSV/Excel/JSON)."""
    __tablename__ = "export_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    format: Mapped[str] = mapped_column(String(10), default="")
    rows: Mapped[int] = mapped_column(Integer, default=0)
    filters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class TelemetryError(Base):
    """Erros (frontend ou backend) reportados."""
    __tablename__ = "telemetry_errors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="frontend")  # frontend/backend
    page: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    stack: Mapped[str] = mapped_column(Text, default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class FeedbackTicket(Base):
    """Mensagens de feedback / suporte enviadas pelos usuários."""
    __tablename__ = "feedback_tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_email: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(40), default="feedback")  # bug/feedback/idea
    subject: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[Text] = mapped_column(Text, default="")
    page: Mapped[str] = mapped_column(String(255), default="")
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open/closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
