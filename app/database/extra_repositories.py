"""Repositórios para WatchItem, WatchEvent e Objection."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, select

from app.database.db import session_scope
from app.database.models import (
    AnalysisCache,
    LeadInteraction,
    Objection,
    WatchEvent,
    WatchItem,
)


def _cache_key(source_input: str, is_website: bool) -> str:
    norm = (source_input or "").strip().lower().rstrip("/")
    raw = f"{int(is_website)}|{norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class AnalysisCacheRepository:
    """Cache de ICPProfile + summary por URL/descrição."""

    DEFAULT_TTL_DAYS = 7

    @staticmethod
    def get(source_input: str, is_website: bool,
            ttl_days: int = DEFAULT_TTL_DAYS) -> dict | None:
        key = _cache_key(source_input, is_website)
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)
        with session_scope() as s:
            row = s.execute(
                select(AnalysisCache).where(AnalysisCache.cache_key == key)
            ).scalar_one_or_none()
            if not row or row.created_at < cutoff:
                return None
            row.hits += 1
            return {
                "icp": row.icp_json or {},
                "summary": row.business_summary or "",
                "created_at": row.created_at,
                "hits": row.hits,
            }

    @staticmethod
    def put(source_input: str, is_website: bool,
            icp: dict, summary: str) -> None:
        key = _cache_key(source_input, is_website)
        with session_scope() as s:
            row = s.execute(
                select(AnalysisCache).where(AnalysisCache.cache_key == key)
            ).scalar_one_or_none()
            if row:
                row.icp_json = icp
                row.business_summary = summary
                row.created_at = datetime.utcnow()
                row.hits = 0
            else:
                s.add(AnalysisCache(
                    cache_key=key,
                    source_input=source_input[:500],
                    is_website=is_website,
                    icp_json=icp,
                    business_summary=summary,
                ))

    @staticmethod
    def invalidate(source_input: str, is_website: bool) -> None:
        key = _cache_key(source_input, is_website)
        with session_scope() as s:
            row = s.execute(
                select(AnalysisCache).where(AnalysisCache.cache_key == key)
            ).scalar_one_or_none()
            if row:
                s.delete(row)

    @staticmethod
    def history_for_url(source_input: str, limit: int = 10) -> list[dict[str, Any]]:
        """Lista todas as análises feitas para o mesmo input (qualquer is_website)."""
        norm = (source_input or "").strip().lower().rstrip("/")
        with session_scope() as s:
            rows = s.execute(
                select(AnalysisCache)
                .where(AnalysisCache.source_input.ilike(f"%{norm}%"))
                .order_by(desc(AnalysisCache.created_at))
                .limit(limit)
            ).scalars().all()
            return [
                {
                    "source_input": r.source_input,
                    "icp": r.icp_json or {},
                    "summary": r.business_summary,
                    "created_at": r.created_at,
                    "hits": r.hits,
                    "products_count": len((r.icp_json or {}).get("products") or []),
                }
                for r in rows
            ]


class LeadInteractionRepository:
    @staticmethod
    def add(lead_id: int, kind: str, content: str = "", channel: str = "") -> int:
        with session_scope() as s:
            obj = LeadInteraction(
                lead_id=lead_id, kind=kind, content=content, channel=channel,
            )
            s.add(obj); s.flush()
            return obj.id

    @staticmethod
    def list_for_lead(lead_id: int, limit: int = 50) -> list[dict[str, Any]]:
        with session_scope() as s:
            rows = s.execute(
                select(LeadInteraction)
                .where(LeadInteraction.lead_id == lead_id)
                .order_by(desc(LeadInteraction.created_at))
                .limit(limit)
            ).scalars().all()
            return [
                {
                    "id": r.id, "lead_id": r.lead_id, "kind": r.kind,
                    "channel": r.channel, "content": r.content,
                    "created_at": r.created_at,
                }
                for r in rows
            ]


class WatchRepository:
    @staticmethod
    def add(name: str, website: str, lead_id: int | None = None,
            interval_days: int = 7) -> int:
        with session_scope() as s:
            existing = s.execute(
                select(WatchItem).where(WatchItem.website == website)
            ).scalar_one_or_none()
            if existing:
                existing.active = True
                return existing.id
            obj = WatchItem(
                name=name, website=website, lead_id=lead_id,
                interval_days=interval_days,
            )
            s.add(obj); s.flush()
            return obj.id

    @staticmethod
    def list_all(active_only: bool = False) -> list[dict[str, Any]]:
        with session_scope() as s:
            stmt = select(WatchItem).order_by(desc(WatchItem.created_at))
            if active_only:
                stmt = stmt.where(WatchItem.active.is_(True))
            rows = s.execute(stmt).scalars().all()
            return [{
                "id": r.id, "lead_id": r.lead_id, "name": r.name,
                "website": r.website, "last_hash": r.last_hash,
                "last_title": r.last_title,
                "last_checked_at": r.last_checked_at,
                "last_change_at": r.last_change_at,
                "interval_days": r.interval_days,
                "active": r.active, "notes": r.notes,
                "created_at": r.created_at,
            } for r in rows]

    @staticmethod
    def update(watch_id: int, **changes) -> None:
        with session_scope() as s:
            obj = s.get(WatchItem, watch_id)
            if not obj:
                return
            for k, v in changes.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)

    @staticmethod
    def remove(watch_id: int) -> None:
        with session_scope() as s:
            obj = s.get(WatchItem, watch_id)
            if obj:
                s.delete(obj)

    @staticmethod
    def add_event(watch_id: int, kind: str, summary: str = "") -> None:
        with session_scope() as s:
            s.add(WatchEvent(watch_id=watch_id, kind=kind, summary=summary))

    @staticmethod
    def recent_events(limit: int = 100) -> list[dict[str, Any]]:
        with session_scope() as s:
            stmt = select(WatchEvent, WatchItem.name, WatchItem.website).join(
                WatchItem, WatchEvent.watch_id == WatchItem.id
            ).order_by(desc(WatchEvent.detected_at)).limit(limit)
            rows = s.execute(stmt).all()
            return [{
                "id": ev.id, "watch_id": ev.watch_id, "kind": ev.kind,
                "summary": ev.summary, "detected_at": ev.detected_at,
                "name": name, "website": website,
            } for ev, name, website in rows]


class ObjectionRepository:
    @staticmethod
    def create(objection_text: str, responses: list[dict], context: str = "") -> int:
        with session_scope() as s:
            obj = Objection(
                objection_text=objection_text,
                context=context,
                responses_json={"items": responses},
            )
            s.add(obj); s.flush()
            return obj.id

    @staticmethod
    def list_recent(limit: int = 50) -> list[dict[str, Any]]:
        with session_scope() as s:
            stmt = select(Objection).order_by(desc(Objection.created_at)).limit(limit)
            rows = s.execute(stmt).scalars().all()
            return [{
                "id": r.id, "objection_text": r.objection_text,
                "context": r.context,
                "responses": (r.responses_json or {}).get("items", []),
                "created_at": r.created_at,
            } for r in rows]
