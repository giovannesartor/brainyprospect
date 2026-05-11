"""Monitoramento de empresas — re-scrape periódico + detecção de mudanças."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Callable

from app.database import WatchRepository
from app.scrapers import scrape_site
from app.services.intelligence import detect_buying_signals, detect_technologies
from app.utils.logger import get_logger

log = get_logger("watch")


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()[:16]


def _excerpt(text: str, n: int = 400) -> str:
    return (text or "").strip()[:n]


def check_one(item: dict) -> dict | None:
    """Faz re-scrape e retorna evento se houve mudança."""
    if not item.get("website"):
        return None
    try:
        site = scrape_site(item["website"])
    except Exception as e:  # noqa: BLE001
        log.debug(f"watch scrape falhou {item['website']}: {e}")
        return None

    text = " ".join(filter(None, [site.title, site.description, site.text]))
    new_hash = _hash(text)
    title = (site.title or "")[:240]

    changes: list[str] = []
    if item.get("last_hash") and item["last_hash"] != new_hash:
        changes.append("conteúdo do site mudou")
    if item.get("last_title") and title and item["last_title"] != title:
        changes.append(f"título mudou: '{item['last_title']}' → '{title}'")

    # detecta novos sinais de compra
    new_signals = detect_buying_signals(text)
    new_techs = detect_technologies(text, getattr(site, "html", "") or "")

    summary = ""
    event = None
    if changes or new_signals:
        summary_parts = changes[:]
        if new_signals:
            summary_parts.append(f"sinais detectados: {', '.join(new_signals[:5])}")
        if new_techs:
            summary_parts.append(f"stack: {', '.join(new_techs[:5])}")
        summary = "; ".join(summary_parts)
        event = {"kind": "site_changed" if changes else "new_signal",
                 "summary": summary}

    WatchRepository.update(
        item["id"],
        last_hash=new_hash,
        last_title=title,
        last_text_excerpt=_excerpt(text),
        last_checked_at=datetime.utcnow(),
        last_change_at=datetime.utcnow() if event else item.get("last_change_at"),
    )
    if event:
        WatchRepository.add_event(item["id"], event["kind"], event["summary"])
    return event


def run_due(progress: Callable[[str, int], None] | None = None) -> int:
    """Roda check em todos os items cujo intervalo venceu. Retorna nº de mudanças."""
    items = WatchRepository.list_all(active_only=True)
    if not items:
        return 0
    n = 0
    total = len(items)
    for i, it in enumerate(items):
        last = it.get("last_checked_at")
        interval = it.get("interval_days") or 7
        if last and (datetime.utcnow() - last) < timedelta(days=interval):
            continue
        if progress:
            progress(f"Verificando {it['name']}…", int((i / total) * 100))
        ev = check_one(it)
        if ev:
            n += 1
    if progress:
        progress("Concluído", 100)
    return n


def run_all_now(progress: Callable[[str, int], None] | None = None) -> int:
    """Força verificação imediata de todos."""
    items = WatchRepository.list_all(active_only=True)
    n = 0
    total = max(1, len(items))
    for i, it in enumerate(items):
        if progress:
            progress(f"Verificando {it['name']}…", int((i / total) * 100))
        ev = check_one(it)
        if ev:
            n += 1
    if progress:
        progress("Concluído", 100)
    return n
