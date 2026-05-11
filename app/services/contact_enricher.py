"""Enriquecimento de um lead a partir do site da empresa."""
from __future__ import annotations

import re
from datetime import datetime

import httpx

from app.models import LeadDraft
from app.scrapers import scrape_site
from app.services.intelligence import (
    classify_company_size,
    detect_buying_signals,
    detect_decision_makers,
    detect_technologies,
    estimate_employees,
    estimate_years_in_market,
    extract_cnpj,
)
from app.utils.contacts import pick_best_phone


def _scrape_instagram_bio(handle_or_url: str, timeout: float = 8.0) -> str:
    """Tenta extrair a bio pública do Instagram via og:description (pré-login).

    Retorna string vazia se falhar.
    """
    if not handle_or_url:
        return ""
    handle = handle_or_url.strip().rstrip("/").split("/")[-1].lstrip("@")
    if not handle or len(handle) > 30:
        return ""
    url = f"https://www.instagram.com/{handle}/"
    try:
        headers = {
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0 Safari/537.36"),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        if r.status_code != 200:
            return ""
        html = r.text
        m = re.search(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        if m:
            txt = m.group(1)
            # remove o prefixo de stats típico ("123 Followers, 45 Following, ...")
            txt = re.sub(r"^[\d\.,KMB ]+(Followers|Seguidores)[^-–:]*[-–:]\s*", "",
                         txt, flags=re.IGNORECASE)
            return txt.strip()[:500]
    except Exception:  # noqa: BLE001
        return ""
    return ""


def enrich_from_website(lead: LeadDraft) -> LeadDraft:
    if not lead.website:
        return lead
    site = scrape_site(lead.website, follow_contact_pages=True)

    if not lead.email and site.emails:
        lead.email = site.emails[0]
    # Telefone: prefere móvel BR válido
    if not lead.phone and site.phones:
        lead.phone = pick_best_phone(site.phones, prefer_mobile=True)
    # WhatsApp: prioriza números extraídos de wa.me / api.whatsapp.com
    # (ali o dono do site EXPLICITAMENTE marcou como WhatsApp)
    wa_nums = getattr(site, "whatsapp_numbers", []) or []
    if not lead.whatsapp:
        if wa_nums:
            lead.whatsapp = pick_best_phone(wa_nums, prefer_mobile=True)
        elif site.whatsapp:
            lead.whatsapp = site.whatsapp[0]
    # Se telefone está vazio mas temos WA confirmado, usa o WA também como phone
    if not lead.phone and wa_nums:
        lead.phone = pick_best_phone(wa_nums, prefer_mobile=True)
    if not lead.instagram and site.instagram:
        lead.instagram = site.instagram[0]
    if not lead.linkedin and site.linkedin:
        lead.linkedin = site.linkedin[0]

    text = (site.title + " " + site.description + " " + site.text)
    html = site.html or ""

    # P5 — Conta sinais já existentes; se tiver 3+, pula IG (economiza ~8s)
    existing_signals = sum(1 for v in (
        lead.email, lead.phone, lead.whatsapp, lead.linkedin,
        getattr(site, "phones", []), getattr(site, "emails", []),
    ) if v)

    # B5: Instagram bio enrichment (caro — só se ainda precisamos)
    ig_bio = ""
    if lead.instagram and existing_signals < 3:
        ig_bio = _scrape_instagram_bio(lead.instagram)
        if ig_bio:
            text = text + " " + ig_bio

    # Inteligência heurística
    if not lead.cnpj:
        lead.cnpj = extract_cnpj(text)
    techs = detect_technologies(html)
    if techs:
        lead.technologies = ", ".join(techs[:10])
    signals = detect_buying_signals(text)
    if signals:
        lead.buying_signals = signals
    decisors = detect_decision_makers(text)
    if decisors:
        lead.decision_makers = decisors
    employees = estimate_employees(text)
    if employees:
        lead.employees_estimate = employees
    years = estimate_years_in_market(text, datetime.utcnow().year)
    if years:
        lead.years_in_market = years
    lead.company_size = classify_company_size(employees, signals)

    extra = lead.extra or {}
    extra["site_excerpt"] = text[:1500]
    if ig_bio:
        extra["instagram_bio"] = ig_bio
    if signals:
        extra["signals"] = signals
    if decisors:
        extra["decision_makers"] = decisors
    if techs:
        extra["technologies"] = techs
    lead.extra = extra
    return lead
