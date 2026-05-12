"""Cliente de IA modular (DeepSeek e OpenAI compartilham a API estilo OpenAI)."""
from __future__ import annotations

import json
import re
import time
from contextvars import ContextVar
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.services.ai.prompts import (
    SYSTEM_SDR,
    prompt_analyze_site,
    prompt_generate_product,
    prompt_qualify_lead,
)
from app.utils.logger import get_logger

log = get_logger("ai")

# Contexto ambiental — quem está chamando a IA (setado pelas rotas).
_ai_user_ctx: ContextVar[int | None] = ContextVar("ai_user_id", default=None)
_ai_feature_ctx: ContextVar[str] = ContextVar("ai_feature", default="generic")


def set_ai_context(user_id: int | None, feature: str) -> None:
    _ai_user_ctx.set(user_id)
    _ai_feature_ctx.set(feature or "generic")


def clear_ai_context() -> None:
    _ai_user_ctx.set(None)
    _ai_feature_ctx.set("generic")


# Tabela de custo (USD por 1M tokens) — aproximada, ajustável.
_PRICING = {
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4-turbo": (10.0, 30.0),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    key = (model or "").lower()
    pin = pout = 0.0
    for name, (i, o) in _PRICING.items():
        if name in key:
            pin, pout = i, o
            break
    return round(((prompt_tokens / 1_000_000) * pin) + ((completion_tokens / 1_000_000) * pout), 6)


class AIClientError(RuntimeError):
    pass


def _build_client() -> tuple[OpenAI, str, float, int]:
    s = get_settings().ai
    if s.default_provider == "openai":
        cfg = s.openai
    else:
        cfg = s.deepseek
    if not cfg.api_key:
        raise AIClientError(
            f"API key do provider '{s.default_provider}' não configurada. "
            "Vá em Configurações para adicioná-la."
        )
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=60.0, max_retries=1)
    return client, cfg.model, cfg.temperature, cfg.max_tokens


def _safe_json(text: str) -> dict[str, Any]:
    """Extrai JSON de uma resposta possivelmente envolta em markdown."""
    if not text:
        return {}
    text = text.strip()
    # remove ```json ... ```
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    # tenta direto
    try:
        return json.loads(text)
    except Exception:
        pass
    # fallback: maior bloco entre chaves
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return {}
    return {}


def _chat(prompt: str, *, system: str = SYSTEM_SDR, json_mode: bool = True) -> dict[str, Any]:
    client, model, temperature, max_tokens = _build_client()
    s = get_settings().ai
    provider = s.default_provider
    feature = _ai_feature_ctx.get()
    uid = _ai_user_ctx.get()

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    started = time.perf_counter()
    resp = None
    try:
        try:
            resp = client.chat.completions.create(**kwargs)
        except TypeError:
            kwargs.pop("response_format", None)
            resp = client.chat.completions.create(**kwargs)
    except Exception as e:  # noqa: BLE001
        latency = int((time.perf_counter() - started) * 1000)
        log.error(f"Falha na chamada IA: {e}")
        _log_usage(uid, provider, model, feature, 0, 0, 0.0, latency,
                   success=False, error=str(e), prompt=prompt, response="")
        raise AIClientError(str(e)) from e

    latency = int((time.perf_counter() - started) * 1000)
    content = resp.choices[0].message.content if resp.choices else ""
    usage = getattr(resp, "usage", None)
    pt = int(getattr(usage, "prompt_tokens", 0) or 0)
    ct = int(getattr(usage, "completion_tokens", 0) or 0)
    cost = _estimate_cost(model, pt, ct)
    _log_usage(uid, provider, model, feature, pt, ct, cost, latency,
               success=True, prompt=prompt, response=content or "")
    return _safe_json(content) if json_mode else {"text": content}


def _log_usage(uid, provider, model, feature, pt, ct, cost, latency,
               *, success: bool, error: str = "", prompt: str = "", response: str = "") -> None:
    try:
        from app.web.audit import log_ai_usage  # import local p/ evitar ciclos
        log_ai_usage(
            user_id=uid, provider=provider, model=model, feature=feature,
            prompt_tokens=pt, completion_tokens=ct, cost_usd=cost,
            latency_ms=latency, success=success, error=error,
            prompt_excerpt=(prompt or "")[:1500],
            response_excerpt=(response or "")[:1500],
        )
    except Exception:
        pass


# ----- API pública -----
def analyze_site(url: str, site_text: str) -> dict[str, Any]:
    return _chat(prompt_analyze_site(url, site_text))


def generate_product(product_name: str, business_summary: str) -> dict[str, Any]:
    """Gera detalhamento (keywords/clients/partners) para um produto específico."""
    return _chat(prompt_generate_product(product_name, business_summary))


def qualify_lead(business_summary: str, lead: dict, mode: str = "direct_sale") -> dict[str, Any]:
    return _chat(prompt_qualify_lead(business_summary, mode, lead))
