"""Scraper genérico de sites: extrai texto, contatos e metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.utils.contacts import (
    domain_of,
    extract_emails,
    extract_instagram,
    extract_linkedin,
    extract_phones,
    extract_whatsapp,
    extract_whatsapp_numbers,
)
from app.utils.http import http_get, polite_sleep
from app.utils.logger import get_logger

log = get_logger("site_scraper")


@dataclass
class SiteData:
    url: str = ""
    title: str = ""
    description: str = ""
    headings: list[str] = field(default_factory=list)
    text: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    whatsapp: list[str] = field(default_factory=list)
    whatsapp_numbers: list[str] = field(default_factory=list)
    instagram: list[str] = field(default_factory=list)
    linkedin: list[str] = field(default_factory=list)
    html: str = ""


def _clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def _find_contact_pages(base_url: str, soup: BeautifulSoup, max_pages: int = 6) -> list[str]:
    keywords = (
        "contato", "contact", "fale", "atendimento", "suporte", "sobre", "about",
        "equipe", "team", "quem-somos", "quem somos", "nossa equipe", "parceiro",
        "parceiros", "partners", "afiliado", "represente",
    )
    found: list[str] = []
    base_dom = domain_of(base_url)
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = urljoin(base_url, href)
        if domain_of(full) != base_dom:
            continue
        low = (href + " " + a.get_text(" ", strip=True)).lower()
        if any(k in low for k in keywords) and full not in found:
            found.append(full)
            if len(found) >= max_pages:
                break
    return found


def scrape_site(url: str, *, follow_contact_pages: bool = True) -> SiteData:
    """Faz scraping leve do site, agregando dados de páginas de contato."""
    if not urlparse(url).scheme:
        url = "https://" + url
    data = SiteData(url=url)
    resp = http_get(url)
    if not resp or not resp.ok:
        log.warning(f"Não foi possível acessar {url}")
        return data
    soup = BeautifulSoup(resp.text, "lxml")
    if soup.title and soup.title.string:
        data.title = soup.title.string.strip()
    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        data.description = md["content"].strip()
    data.headings = [
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h1", "h2", "h3"])
        if h.get_text(strip=True)
    ][:30]
    raw_text = _clean_text(soup)
    raw_html = resp.text
    aggregate_text = raw_text
    aggregate_html = raw_html

    if follow_contact_pages:
        for sub_url in _find_contact_pages(url, soup):
            polite_sleep()
            sub_resp = http_get(sub_url)
            if not sub_resp or not sub_resp.ok:
                continue
            sub_soup = BeautifulSoup(sub_resp.text, "lxml")
            aggregate_text += " " + _clean_text(sub_soup)
            aggregate_html += " " + sub_resp.text

    data.text = aggregate_text[:20000]
    data.html = aggregate_html[:60000]
    data.emails = extract_emails(aggregate_text + " " + aggregate_html)
    data.phones = extract_phones(aggregate_text)
    data.whatsapp = extract_whatsapp(aggregate_html)
    data.whatsapp_numbers = extract_whatsapp_numbers(aggregate_html + " " + aggregate_text)
    data.instagram = extract_instagram(aggregate_html)
    data.linkedin = extract_linkedin(aggregate_html)
    return data
