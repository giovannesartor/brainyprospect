"""Scraper Bing (HTML público) usado como fonte secundária de leads."""
from __future__ import annotations

from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from app.utils.http import http_get, polite_sleep
from app.utils.logger import get_logger

log = get_logger("bing")


def search_bing(query: str, *, max_results: int = 25) -> list[dict]:
    """Retorna lista de resultados {title, url, snippet}."""
    results: list[dict] = []
    seen: set[str] = set()
    per_page = 10
    pages = max(1, (max_results + per_page - 1) // per_page)
    for page in range(pages):
        first = page * per_page + 1
        url = f"https://www.bing.com/search?q={quote_plus(query)}&first={first}&setlang=pt-BR"
        resp = http_get(url, headers={"Accept-Language": "pt-BR,pt;q=0.9"})
        if not resp or not resp.ok:
            break
        soup = BeautifulSoup(resp.text, "lxml")
        for li in soup.select("li.b_algo"):
            a = li.find("a", href=True)
            if not a:
                continue
            link = a["href"]
            host = urlparse(link).hostname or ""
            if host in seen:
                continue
            seen.add(host)
            snippet_el = li.select_one(".b_caption p") or li.select_one("p")
            results.append({
                "title": a.get_text(" ", strip=True),
                "url": link,
                "snippet": snippet_el.get_text(" ", strip=True) if snippet_el else "",
            })
            if len(results) >= max_results:
                return results
        polite_sleep()
    return results
