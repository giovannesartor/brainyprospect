"""Utilitários de rede e anti-bloqueio."""
from __future__ import annotations

import random
import time
from typing import Iterable

import httpx
import requests
from fake_useragent import UserAgent

from app.config import get_settings

_ua = UserAgent(fallback=(
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
))


def random_user_agent() -> str:
    settings = get_settings()
    if not settings.scraping.user_agent_rotation:
        return _ua.fallback  # type: ignore[attr-defined]
    try:
        return _ua.random
    except Exception:
        return _ua.fallback  # type: ignore[attr-defined]


def polite_sleep() -> None:
    s = get_settings().scraping
    delay = random.uniform(s.min_delay_ms, s.max_delay_ms) / 1000.0
    time.sleep(delay)


def default_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {
        "User-Agent": random_user_agent(),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if extra:
        h.update(extra)
    return h


def _proxies() -> dict[str, str] | None:
    proxy = get_settings().scraping.proxy
    return {"http": proxy, "https": proxy} if proxy else None


def http_get(url: str, *, headers: dict[str, str] | None = None,
             timeout: int | None = None, retries: int | None = None,
             use_cache: bool = True) -> requests.Response | None:
    s = get_settings().scraping
    timeout = timeout or s.timeout_seconds
    retries = retries or s.max_retries
    # P3 — cache em memória (TTL 1h, só cabeçalhos default)
    cache_key = url if (use_cache and not headers) else None
    if cache_key:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                url,
                headers=default_headers(headers),
                timeout=timeout,
                proxies=_proxies(),
                allow_redirects=True,
            )
            if resp.status_code in (429, 503):
                polite_sleep()
                continue
            if cache_key and resp.status_code == 200:
                _cache_put(cache_key, resp)
            return resp
        except Exception as e:  # noqa: BLE001
            last_exc = e
            polite_sleep()
    if last_exc:
        from app.utils.logger import get_logger
        get_logger("net").debug(f"GET falhou {url}: {last_exc}")
    return None


# ---------------------------------------------------------------------------
# P3 — cache HTTP simples em memória, TTL e tamanho limitado
# ---------------------------------------------------------------------------
_HTTP_CACHE: dict[str, tuple[float, requests.Response]] = {}
_HTTP_CACHE_TTL = 3600.0  # 1h
_HTTP_CACHE_MAX = 500


def _cache_get(key: str) -> requests.Response | None:
    item = _HTTP_CACHE.get(key)
    if not item:
        return None
    ts, resp = item
    if time.time() - ts > _HTTP_CACHE_TTL:
        _HTTP_CACHE.pop(key, None)
        return None
    return resp


def _cache_put(key: str, resp: requests.Response) -> None:
    if len(_HTTP_CACHE) >= _HTTP_CACHE_MAX:
        # remove o mais antigo
        oldest = min(_HTTP_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _HTTP_CACHE.pop(oldest, None)
    _HTTP_CACHE[key] = (time.time(), resp)


def http_cache_clear() -> None:
    _HTTP_CACHE.clear()


async def async_http_get(url: str, *, headers: dict[str, str] | None = None,
                         timeout: int | None = None) -> httpx.Response | None:
    s = get_settings().scraping
    timeout = timeout or s.timeout_seconds
    try:
        async with httpx.AsyncClient(
            headers=default_headers(headers),
            timeout=timeout,
            follow_redirects=True,
            proxies=get_settings().scraping.proxy or None,
        ) as client:
            return await client.get(url)
    except Exception:
        return None


def chunked(it: Iterable, size: int):
    buf: list = []
    for x in it:
        buf.append(x)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf
