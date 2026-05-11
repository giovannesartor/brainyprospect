"""Scraper do Google Maps via Playwright (browser real, headless)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable

try:  # Playwright é opcional (não instalado por padrão na versão web)
    from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    Page = None  # type: ignore[assignment]
    PWTimeout = Exception  # type: ignore[assignment,misc]
    sync_playwright = None  # type: ignore[assignment]
    _PLAYWRIGHT_AVAILABLE = False

from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger("gmaps")


@dataclass
class MapsPlace:
    name: str = ""
    niche: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    phone: str = ""
    website: str = ""
    rating: float | None = None
    reviews: int | None = None


def _parse_rating(text: str) -> tuple[float | None, int | None]:
    rating = None
    reviews = None
    m = re.search(r"(\d[.,]\d)", text)
    if m:
        try:
            rating = float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    m2 = re.search(r"\((\d[\d.\s]*)\)", text)
    if m2:
        digits = re.sub(r"\D", "", m2.group(1))
        if digits:
            reviews = int(digits)
    return rating, reviews


def _split_city_state(address: str) -> tuple[str, str]:
    if not address:
        return "", ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 2:
        last = parts[-1]
        prev = parts[-2]
        # tenta detectar "Cidade - UF"
        m = re.match(r"^(.*?)\s*-\s*([A-Z]{2})$", last)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return prev, last
    return parts[0], ""


def _scroll_results(page: Page, target: int) -> None:
    """Rola o painel de resultados até carregar 'target' itens."""
    try:
        feed = page.locator('div[role="feed"]').first
        feed.wait_for(timeout=10000)
    except PWTimeout:
        return
    last_count = 0
    stagnant = 0
    while True:
        items = page.locator('div[role="feed"] > div > div[jsaction]')
        count = items.count()
        if count >= target:
            return
        if count == last_count:
            stagnant += 1
            if stagnant >= 4:
                return
        else:
            stagnant = 0
        last_count = count
        page.mouse.wheel(0, 6000)
        page.wait_for_timeout(1200)


def _extract_card(card) -> MapsPlace:
    place = MapsPlace()
    try:
        place.name = card.locator(".qBF1Pd, .fontHeadlineSmall").first.inner_text(timeout=2000).strip()
    except Exception:
        place.name = (card.get_attribute("aria-label") or "").strip()
    text = card.inner_text(timeout=2000) if card else ""
    # rating / reviews
    place.rating, place.reviews = _parse_rating(text)
    # endereço heurístico — última linha que contenha vírgula
    for line in text.split("\n"):
        line = line.strip()
        if "·" in line and not place.niche:
            # ex.: "Restaurante · R. Foo, 123"
            parts = [p.strip() for p in line.split("·") if p.strip()]
            if parts:
                place.niche = parts[0]
                if len(parts) > 1:
                    place.address = parts[-1]
        elif "," in line and not place.address:
            place.address = line
    place.city, place.state = _split_city_state(place.address)
    return place


def _extract_detail(page: Page) -> dict:
    """Após clicar num card, extrai telefone e site do painel lateral."""
    out = {"phone": "", "website": ""}
    try:
        page.wait_for_selector('button[data-item-id^="phone"], a[data-item-id="authority"]', timeout=8000)
    except PWTimeout:
        return out
    # telefone
    try:
        btn = page.locator('button[data-item-id^="phone"]').first
        if btn and btn.count():
            label = btn.get_attribute("aria-label") or btn.inner_text()
            out["phone"] = re.sub(r"^[^\d+]*", "", label or "").strip()
    except Exception:
        pass
    # website
    try:
        link = page.locator('a[data-item-id="authority"]').first
        if link and link.count():
            out["website"] = link.get_attribute("href") or ""
    except Exception:
        pass
    return out


def search_google_maps(query: str, *, max_results: int = 20) -> list[MapsPlace]:
    """Busca empresas no Google Maps e retorna lista de MapsPlace."""
    if not _PLAYWRIGHT_AVAILABLE:
        log.warning("Playwright não disponível — Google Maps desativado nesta instalação.")
        return []
    settings = get_settings().scraping
    results: list[MapsPlace] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=settings.headless,
                                     args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()
        try:
            page.goto(f"https://www.google.com/maps/search/{query.replace(' ', '+')}?hl=pt-BR",
                      wait_until="domcontentloaded", timeout=settings.timeout_seconds * 1000)
            try:
                # consent dialog (UE) — clicar se aparecer
                page.click('button:has-text("Aceitar tudo")', timeout=2500)
            except Exception:
                pass
            _scroll_results(page, max_results)
            cards = page.locator('div[role="feed"] > div > div[jsaction]')
            total = min(cards.count(), max_results)
            for i in range(total):
                try:
                    card = cards.nth(i)
                    card.scroll_into_view_if_needed(timeout=2000)
                    place = _extract_card(card)
                    if not place.name:
                        continue
                    # abrir detalhe
                    try:
                        card.click(timeout=3000)
                        page.wait_for_timeout(900)
                        detail = _extract_detail(page)
                        place.phone = detail.get("phone", "")
                        place.website = detail.get("website", "")
                    except Exception:
                        pass
                    results.append(place)
                except Exception as e:  # noqa: BLE001
                    log.debug(f"Card {i} falhou: {e}")
                    continue
        finally:
            browser.close()
    return results


def ensure_browsers_installed() -> None:
    """Helper: instrui o usuário a rodar `playwright install chromium` se faltar."""
    try:
        with sync_playwright() as pw:
            pw.chromium.launch(headless=True).close()
    except Exception as e:  # noqa: BLE001
        log.error(
            "Playwright/Chromium não instalado. Rode: "
            "`python -m playwright install chromium`. Erro: " + str(e)
        )
        raise
