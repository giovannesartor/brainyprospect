"""Scraper DuckDuckGo HTML (lite, sem JS) — 3ª fonte de leads."""
from __future__ import annotations

from urllib.parse import quote_plus, unquote, urlparse

from bs4 import BeautifulSoup

from app.utils.http import http_get, polite_sleep
from app.utils.logger import get_logger

log = get_logger("ddg")


def _clean_ddg_url(href: str) -> str:
    """DDG embrulha URLs em /l/?uddg=...; descompacta."""
    if not href:
        return ""
    if href.startswith("//duckduckgo.com/l/"):
        href = "https:" + href
    if "uddg=" in href:
        try:
            part = href.split("uddg=", 1)[1].split("&", 1)[0]
            return unquote(part)
        except Exception:  # noqa: BLE001
            return href
    return href


def search_duckduckgo(query: str, *, max_results: int = 20) -> list[dict]:
    """Retorna lista de resultados {title, url, snippet}."""
    results: list[dict] = []
    seen: set[str] = set()
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=br-pt"
    resp = http_get(url, headers={
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer": "https://duckduckgo.com/",
    })
    if not resp or not resp.ok:
        return results
    soup = BeautifulSoup(resp.text, "lxml")
    for res in soup.select("div.result, div.web-result"):
        a = res.select_one("a.result__a") or res.find("a", href=True)
        if not a:
            continue
        link = _clean_ddg_url(a.get("href", ""))
        if not link:
            continue
        host = urlparse(link).hostname or ""
        if host in seen:
            continue
        seen.add(host)
        snip = res.select_one(".result__snippet")
        results.append({
            "title": a.get_text(" ", strip=True),
            "url": link,
            "snippet": snip.get_text(" ", strip=True) if snip else "",
        })
        if len(results) >= max_results:
            break
    polite_sleep()
    return results
