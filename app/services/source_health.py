"""Verifica saúde das fontes de busca (Bing, DDG, Google Maps/Playwright, IA).

Uso típico: chamar `check_all()` em background quando a Search Page abre.
Retorna dict {source: {"ok": bool, "detail": str, "checked_at": datetime}}.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

from app.utils.logger import get_logger

log = get_logger("health")


@dataclass
class SourceStatus:
    name: str
    ok: bool
    detail: str = ""
    checked_at: datetime | None = None


def _check_bing() -> SourceStatus:
    try:
        from app.scrapers import search_bing
        r = search_bing("teste contabilidade", max_results=2)
        ok = len(r) > 0
        return SourceStatus(
            "Bing", ok,
            f"{len(r)} resultados" if ok else "0 resultados (HTML pode ter mudado)",
            datetime.utcnow(),
        )
    except Exception as e:  # noqa: BLE001
        return SourceStatus("Bing", False, str(e)[:80], datetime.utcnow())


def _check_ddg() -> SourceStatus:
    try:
        from app.scrapers import search_duckduckgo
        r = search_duckduckgo("teste contabilidade", max_results=2)
        ok = len(r) > 0
        return SourceStatus(
            "DuckDuckGo", ok,
            f"{len(r)} resultados" if ok else "0 resultados",
            datetime.utcnow(),
        )
    except Exception as e:  # noqa: BLE001
        return SourceStatus("DuckDuckGo", False, str(e)[:80], datetime.utcnow())


def _check_playwright() -> SourceStatus:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                return SourceStatus(
                    "Google Maps", True, "Playwright OK", datetime.utcnow(),
                )
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                if "Executable doesn't exist" in msg or "playwright install" in msg.lower():
                    return SourceStatus(
                        "Google Maps", False,
                        "Rode: .venv/bin/python -m playwright install chromium",
                        datetime.utcnow(),
                    )
                return SourceStatus("Google Maps", False, msg[:80], datetime.utcnow())
    except ImportError:
        return SourceStatus(
            "Google Maps", False, "Playwright não instalado", datetime.utcnow(),
        )


def _check_ai() -> SourceStatus:
    try:
        from app.config import get_settings
        s = get_settings().ai
        cfg = s.openai if s.default_provider == "openai" else s.deepseek
        if not cfg.api_key:
            return SourceStatus(
                "IA", False,
                f"API key '{s.default_provider}' ausente — Configurações",
                datetime.utcnow(),
            )
        return SourceStatus(
            "IA", True, f"{s.default_provider} · {cfg.model}", datetime.utcnow(),
        )
    except Exception as e:  # noqa: BLE001
        return SourceStatus("IA", False, str(e)[:80], datetime.utcnow())


def check_all(include_playwright: bool = False) -> list[SourceStatus]:
    """Roda todos checks em paralelo. Playwright é opcional pois é lento."""
    checks = [_check_ai, _check_bing, _check_ddg]
    if include_playwright:
        checks.append(_check_playwright)
    out: list[SourceStatus] = []
    with ThreadPoolExecutor(max_workers=len(checks)) as ex:
        for status in ex.map(lambda f: f(), checks):
            out.append(status)
    return out
