"""Cliente de IA modular (DeepSeek e OpenAI compartilham a API estilo OpenAI)."""
from __future__ import annotations

import json
import re
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
        # DeepSeek e OpenAI suportam response_format json_object
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs)
    except TypeError:
        kwargs.pop("response_format", None)
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:  # noqa: BLE001
        log.error(f"Falha na chamada IA: {e}")
        raise AIClientError(str(e)) from e

    content = resp.choices[0].message.content if resp.choices else ""
    return _safe_json(content) if json_mode else {"text": content}


# ----- API pública -----
def analyze_site(url: str, site_text: str) -> dict[str, Any]:
    return _chat(prompt_analyze_site(url, site_text))


def generate_product(product_name: str, business_summary: str) -> dict[str, Any]:
    """Gera detalhamento (keywords/clients/partners) para um produto específico."""
    return _chat(prompt_generate_product(product_name, business_summary))


def qualify_lead(business_summary: str, lead: dict, mode: str = "direct_sale") -> dict[str, Any]:
    return _chat(prompt_qualify_lead(business_summary, mode, lead))
