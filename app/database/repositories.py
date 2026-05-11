"""Repository pattern para Leads e Searches."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import and_, desc, func, or_, select

from app.database.db import session_scope
from app.database.models import Campaign, ExportRecord, Lead, Search


# ---------- SEARCHES ----------
class SearchRepository:
    @staticmethod
    def create(**kwargs) -> int:
        with session_scope() as s:
            obj = Search(**kwargs)
            s.add(obj)
            s.flush()
            return obj.id

    @staticmethod
    def update_total(search_id: int, total: int) -> None:
        with session_scope() as s:
            obj = s.get(Search, search_id)
            if obj:
                obj.total_leads = total

    @staticmethod
    def list_recent(limit: int = 20) -> list[dict[str, Any]]:
        with session_scope() as s:
            stmt = select(Search).order_by(desc(Search.created_at)).limit(limit)
            rows = s.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "input": r.source_input,
                    "niche": r.niche,
                    "city": r.city,
                    "total": r.total_leads,
                    "created_at": r.created_at,
                }
                for r in rows
            ]


# ---------- LEADS ----------
class LeadRepository:
    @staticmethod
    def upsert_many(leads: Iterable[dict[str, Any]]) -> int:
        """Insere leads evitando duplicatas óbvias (nome+cidade+telefone).

        Faz dedup intra-lote (modos diferentes podem trazer o mesmo lead) e
        flush após cada add para que o select consiga enxergar o anterior.
        """
        inserted = 0
        seen_keys: set[tuple[str, str, str]] = set()
        with session_scope() as s:
            for data in leads:
                name = (data.get("name") or "").strip()
                city = (data.get("city") or "").strip()
                phone = (data.get("phone") or "").strip()
                key = (name.lower(), city.lower(), phone)
                if key in seen_keys:
                    # já está no lote — atualiza o que tinha sido adicionado
                    stmt = select(Lead).where(
                        and_(Lead.name == name, Lead.city == city, Lead.phone == phone)
                    )
                    exists = s.execute(stmt).scalar_one_or_none()
                    if exists:
                        for k, v in data.items():
                            if hasattr(exists, k) and v and not getattr(exists, k):
                                setattr(exists, k, v)
                    continue
                seen_keys.add(key)
                stmt = select(Lead).where(
                    and_(Lead.name == name, Lead.city == city, Lead.phone == phone)
                )
                exists = s.execute(stmt).scalar_one_or_none()
                if exists:
                    for k, v in data.items():
                        if hasattr(exists, k) and v and not getattr(exists, k):
                            setattr(exists, k, v)
                    continue
                # normaliza campos para evitar None onde unique exige string
                data_norm = dict(data)
                data_norm["name"] = name
                data_norm["city"] = city
                data_norm["phone"] = phone
                try:
                    obj = Lead(**data_norm)
                    s.add(obj)
                    s.flush()  # garante que próximo select enxergue
                    inserted += 1
                except Exception:
                    s.rollback()
                    # tenta de novo localizando e atualizando
                    exists = s.execute(stmt).scalar_one_or_none()
                    if exists:
                        for k, v in data.items():
                            if hasattr(exists, k) and v and not getattr(exists, k):
                                setattr(exists, k, v)
        return inserted

    @staticmethod
    def update(lead_id: int, **changes) -> None:
        with session_scope() as s:
            obj = s.get(Lead, lead_id)
            if not obj:
                return
            for k, v in changes.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)

    @staticmethod
    def query(
        *,
        text: str = "",
        city: str | None = None,
        state: str | None = None,
        niche: str | None = None,
        min_score: int = 0,
        only_with_email: bool = False,
        only_with_whatsapp: bool = False,
        only_without_site: bool = False,
        prospection_mode: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        campaign_id: int | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with session_scope() as s:
            stmt = select(Lead)
            conditions = []
            if text:
                like = f"%{text}%"
                conditions.append(or_(
                    Lead.name.ilike(like),
                    Lead.email.ilike(like),
                    Lead.niche.ilike(like),
                    Lead.city.ilike(like),
                ))
            if city:
                conditions.append(Lead.city.ilike(f"%{city}%"))
            if state:
                conditions.append(Lead.state.ilike(f"%{state}%"))
            if niche:
                conditions.append(Lead.niche.ilike(f"%{niche}%"))
            if min_score:
                conditions.append(Lead.score >= min_score)
            if only_with_email:
                conditions.append(and_(Lead.email != "", Lead.email.isnot(None)))
            if only_with_whatsapp:
                conditions.append(and_(Lead.whatsapp != "", Lead.whatsapp.isnot(None)))
            if only_without_site:
                conditions.append(or_(Lead.website == "", Lead.website.is_(None)))
            if prospection_mode in ("direct_sale", "partners"):
                conditions.append(Lead.prospection_mode == prospection_mode)
            if priority in ("maxima", "alta", "media", "baixa"):
                conditions.append(Lead.priority == priority)
            if status:
                conditions.append(Lead.status == status)
            if campaign_id:
                conditions.append(Lead.campaign_id == campaign_id)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(desc(Lead.score), desc(Lead.created_at)).limit(limit).offset(offset)
            rows = s.execute(stmt).scalars().all()
            return [LeadRepository._to_dict(r) for r in rows]

    @staticmethod
    def get(lead_id: int) -> dict[str, Any] | None:
        with session_scope() as s:
            obj = s.get(Lead, lead_id)
            return LeadRepository._to_dict(obj) if obj else None

    @staticmethod
    def stats() -> dict[str, Any]:
        with session_scope() as s:
            total = s.execute(select(func.count(Lead.id))).scalar_one()
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = s.execute(
                select(func.count(Lead.id)).where(Lead.created_at >= today)
            ).scalar_one()
            avg = s.execute(select(func.avg(Lead.score))).scalar() or 0
            niche_rows = s.execute(
                select(Lead.niche, func.count(Lead.id))
                .where(Lead.niche != "")
                .group_by(Lead.niche)
                .order_by(desc(func.count(Lead.id)))
                .limit(8)
            ).all()
            week = datetime.utcnow() - timedelta(days=7)
            weekly = s.execute(
                select(func.count(Lead.id)).where(Lead.created_at >= week)
            ).scalar_one()
            direct_count = s.execute(
                select(func.count(Lead.id)).where(Lead.prospection_mode == "direct_sale")
            ).scalar_one()
            partners_count = s.execute(
                select(func.count(Lead.id)).where(Lead.prospection_mode == "partners")
            ).scalar_one()
            avg_direct = s.execute(
                select(func.avg(Lead.score)).where(Lead.prospection_mode == "direct_sale")
            ).scalar() or 0
            avg_partners = s.execute(
                select(func.avg(Lead.score)).where(Lead.prospection_mode == "partners")
            ).scalar() or 0
            return {
                "total": int(total or 0),
                "today": int(today_count or 0),
                "weekly": int(weekly or 0),
                "avg_score": round(float(avg), 1),
                "top_niches": [(n or "—", int(c)) for n, c in niche_rows],
                "direct_total": int(direct_count or 0),
                "partners_total": int(partners_count or 0),
                "avg_score_direct": round(float(avg_direct), 1),
                "avg_score_partners": round(float(avg_partners), 1),
            }

    @staticmethod
    def pipeline_stats() -> dict[str, int]:
        """Contagem de leads por status (CRM Kanban)."""
        statuses = ("novo", "qualificado", "contatado", "respondeu",
                    "reuniao", "proposta", "fechado", "perdido")
        with session_scope() as s:
            out: dict[str, int] = {}
            for st in statuses:
                n = s.execute(
                    select(func.count(Lead.id)).where(Lead.status == st)
                ).scalar_one()
                out[st] = int(n or 0)
            return out

    @staticmethod
    def priority_distribution() -> dict[str, int]:
        with session_scope() as s:
            out: dict[str, int] = {}
            for p in ("maxima", "alta", "media", "baixa"):
                n = s.execute(
                    select(func.count(Lead.id)).where(Lead.priority == p)
                ).scalar_one()
                out[p] = int(n or 0)
            return out

    # ---------------- bulk + analytics adicionais ----------------
    @staticmethod
    def bulk_update_status(ids: list[int], status: str) -> int:
        if not ids:
            return 0
        with session_scope() as s:
            n = 0
            for lid in ids:
                obj = s.get(Lead, lid)
                if obj:
                    obj.status = status
                    n += 1
            return n

    @staticmethod
    def bulk_assign_campaign(ids: list[int], campaign_id: int | None) -> int:
        if not ids:
            return 0
        with session_scope() as s:
            n = 0
            for lid in ids:
                obj = s.get(Lead, lid)
                if obj:
                    obj.campaign_id = campaign_id
                    n += 1
            return n

    @staticmethod
    def delete_many(ids: list[int]) -> int:
        if not ids:
            return 0
        with session_scope() as s:
            n = 0
            for lid in ids:
                obj = s.get(Lead, lid)
                if obj:
                    s.delete(obj); n += 1
            return n

    @staticmethod
    def delete_all(*, also_searches: bool = True, also_interactions: bool = True) -> int:
        """Apaga TODOS os leads. Por padrão também apaga buscas e interações."""
        from app.database.models import LeadInteraction
        with session_scope() as s:
            n = s.query(Lead).count()
            if also_interactions:
                s.query(LeadInteraction).delete(synchronize_session=False)
            s.query(Lead).delete(synchronize_session=False)
            if also_searches:
                s.query(Search).delete(synchronize_session=False)
            return n

    @staticmethod
    def leads_per_day(days: int = 14) -> list[tuple[str, int]]:
        from datetime import date
        out: list[tuple[str, int]] = []
        with session_scope() as s:
            today = date.today()
            for i in range(days - 1, -1, -1):
                d = today - timedelta(days=i)
                start = datetime(d.year, d.month, d.day)
                end = start + timedelta(days=1)
                n = s.execute(
                    select(func.count(Lead.id)).where(
                        and_(Lead.created_at >= start, Lead.created_at < end)
                    )
                ).scalar_one()
                out.append((d.strftime("%d/%m"), int(n or 0)))
        return out

    @staticmethod
    def top_cities(n: int = 8) -> list[tuple[str, int]]:
        with session_scope() as s:
            rows = s.execute(
                select(Lead.city, func.count(Lead.id))
                .where(Lead.city.isnot(None), Lead.city != "")
                .group_by(Lead.city)
                .order_by(desc(func.count(Lead.id)))
                .limit(n)
            ).all()
            return [(c or "—", int(k)) for c, k in rows]

    @staticmethod
    def all_for_recompute() -> list[dict[str, Any]]:
        with session_scope() as s:
            rows = s.execute(select(Lead)).scalars().all()
            return [LeadRepository._to_dict(r) for r in rows]

    @staticmethod
    def update_priority_score(lead_id: int, match_score: int, priority: str) -> None:
        with session_scope() as s:
            obj = s.get(Lead, lead_id)
            if obj:
                obj.match_score = match_score
                obj.priority = priority

    @staticmethod
    def update_send_status(lead_id: int, send_status: str) -> None:
        with session_scope() as s:
            obj = s.get(Lead, lead_id)
            if obj:
                obj.send_status = send_status
                if send_status == "enviado":
                    obj.last_contact_at = datetime.utcnow()
                    if obj.followup_step < 1:
                        obj.followup_step = 1

    @staticmethod
    def set_messages(lead_id: int, message_a: str, message_b: str = "",
                     message_opener: str = "", message_tone: str = "",
                     hot_score: int | None = None) -> None:
        with session_scope() as s:
            obj = s.get(Lead, lead_id)
            if not obj:
                return
            if message_a is not None:
                obj.message_a = message_a
            if message_b is not None:
                obj.message_b = message_b
            if message_opener is not None:
                obj.message_opener = message_opener
            if message_tone is not None:
                obj.message_tone = message_tone
            if hot_score is not None:
                obj.hot_score = int(hot_score)

    @staticmethod
    def today_list(limit: int = 10) -> list[dict[str, Any]]:
        """Top leads para abordar HOJE: prioriza hot_score x não enviados ainda."""
        with session_scope() as s:
            stmt = (
                select(Lead)
                .where(Lead.send_status == "nao_enviado")
                .order_by(desc(Lead.hot_score), desc(Lead.match_score), desc(Lead.score))
                .limit(limit)
            )
            rows = s.execute(stmt).scalars().all()
            return [LeadRepository._to_dict(r) for r in rows]

    @staticmethod
    def due_followups(now: datetime | None = None) -> list[dict[str, Any]]:
        """Leads cujo próximo follow-up venceu."""
        now = now or datetime.utcnow()
        with session_scope() as s:
            stmt = (
                select(Lead)
                .where(and_(
                    Lead.next_followup_at.isnot(None),
                    Lead.next_followup_at <= now,
                    Lead.send_status.notin_(["respondido", "fechado", "perdido"]),
                ))
                .order_by(Lead.next_followup_at)
            )
            rows = s.execute(stmt).scalars().all()
            return [LeadRepository._to_dict(r) for r in rows]

    @staticmethod
    def schedule_next_followup(lead_id: int, days: int) -> None:
        with session_scope() as s:
            obj = s.get(Lead, lead_id)
            if obj:
                obj.next_followup_at = datetime.utcnow() + timedelta(days=days)

    @staticmethod
    def advance_followup_step(lead_id: int) -> int:
        with session_scope() as s:
            obj = s.get(Lead, lead_id)
            if not obj:
                return 0
            obj.followup_step = (obj.followup_step or 0) + 1
            return obj.followup_step

    @staticmethod
    def _to_dict(r: Lead) -> dict[str, Any]:
        return {
            "id": r.id,
            "name": r.name,
            "niche": r.niche,
            "city": r.city,
            "state": r.state,
            "country": r.country,
            "address": r.address,
            "website": r.website,
            "phone": r.phone,
            "whatsapp": r.whatsapp,
            "email": r.email,
            "instagram": r.instagram,
            "linkedin": r.linkedin,
            "google_rating": r.google_rating,
            "google_reviews": r.google_reviews,
            "score": r.score,
            "score_reason": r.score_reason,
            "pitch": r.pitch,
            "status": r.status,
            "prospection_mode": r.prospection_mode,
            "tags": r.tags,
            "cnpj": r.cnpj,
            "company_size": r.company_size,
            "employees_estimate": r.employees_estimate,
            "years_in_market": r.years_in_market,
            "technologies": r.technologies,
            "decision_makers": r.decision_makers,
            "buying_signals": r.buying_signals,
            "match_score": r.match_score,
            "priority": r.priority,
            "why_matters": r.why_matters,
            "opportunity_when": r.opportunity_when,
            "opportunity_channel": r.opportunity_channel,
            "opportunity_offer": r.opportunity_offer,
            "ticket_estimate": r.ticket_estimate,
            "revenue_year_estimate": r.revenue_year_estimate,
            "observations": r.observations,
            "follow_up_text": r.follow_up_text,
            "last_contact_at": r.last_contact_at,
            "next_followup_at": r.next_followup_at,
            "campaign_id": r.campaign_id,
            "message_a": r.message_a,
            "message_b": r.message_b,
            "message_opener": r.message_opener,
            "message_tone": r.message_tone,
            "send_status": r.send_status,
            "hot_score": r.hot_score,
            "followup_step": r.followup_step,
            "created_at": r.created_at,
        }


class CampaignRepository:
    @staticmethod
    def create(name: str, description: str = "", target_mode: str = "direct_sale",
               color: str = "#6366F1") -> int:
        with session_scope() as s:
            existing = s.execute(select(Campaign).where(Campaign.name == name)).scalar_one_or_none()
            if existing:
                return existing.id
            obj = Campaign(name=name, description=description,
                           target_mode=target_mode, color=color)
            s.add(obj); s.flush()
            return obj.id

    @staticmethod
    def list_all() -> list[dict[str, Any]]:
        with session_scope() as s:
            rows = s.execute(select(Campaign).order_by(desc(Campaign.created_at))).scalars().all()
            results = []
            for c in rows:
                lead_count = s.execute(
                    select(func.count(Lead.id)).where(Lead.campaign_id == c.id)
                ).scalar_one()
                avg_score = s.execute(
                    select(func.avg(Lead.score)).where(Lead.campaign_id == c.id)
                ).scalar() or 0
                won = s.execute(
                    select(func.count(Lead.id)).where(
                        and_(Lead.campaign_id == c.id, Lead.status == "fechado")
                    )
                ).scalar_one()
                results.append({
                    "id": c.id, "name": c.name, "description": c.description,
                    "target_mode": c.target_mode, "color": c.color,
                    "created_at": c.created_at,
                    "lead_count": int(lead_count or 0),
                    "avg_score": round(float(avg_score), 1),
                    "won": int(won or 0),
                })
            return results

    @staticmethod
    def assign_leads(campaign_id: int, lead_ids: list[int]) -> int:
        if not lead_ids:
            return 0
        with session_scope() as s:
            n = 0
            for lid in lead_ids:
                obj = s.get(Lead, lid)
                if obj:
                    obj.campaign_id = campaign_id
                    n += 1
            return n

    @staticmethod
    def delete(campaign_id: int) -> None:
        with session_scope() as s:
            obj = s.get(Campaign, campaign_id)
            if obj:
                # leads ficam sem campanha (FK ON DELETE SET NULL)
                s.delete(obj)


class ExportRepository:
    @staticmethod
    def register(file_path: str, fmt: str, rows: int) -> None:
        with session_scope() as s:
            s.add(ExportRecord(file_path=file_path, format=fmt, rows=rows))

    @staticmethod
    def list_recent(limit: int = 30) -> list[dict[str, Any]]:
        with session_scope() as s:
            rows = s.execute(
                select(ExportRecord).order_by(desc(ExportRecord.created_at)).limit(limit)
            ).scalars().all()
            return [
                {"id": r.id, "file": r.file_path, "format": r.format,
                 "rows": r.rows, "created_at": r.created_at}
                for r in rows
            ]
