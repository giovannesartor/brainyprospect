"""Carrega, valida e persiste as configurações do app."""
from __future__ import annotations

import json
import shutil
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from app.paths import DEFAULT_SETTINGS_FILE, SETTINGS_FILE


class DeepSeekSettings(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    temperature: float = 0.4
    max_tokens: int = 1500


class OpenAISettings(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.4
    max_tokens: int = 1500


class AISettings(BaseModel):
    default_provider: str = "deepseek"
    deepseek: DeepSeekSettings = Field(default_factory=DeepSeekSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)


class ScrapingSettings(BaseModel):
    timeout_seconds: int = 25
    min_delay_ms: int = 800
    max_delay_ms: int = 2400
    max_retries: int = 3
    max_results_per_search: int = 40
    user_agent_rotation: bool = True
    proxy: str = ""
    headless: bool = True


class AppSettings(BaseModel):
    default_country: str = "Brasil"
    default_language: str = "pt-BR"
    theme: str = "dark"


_DEFAULT_PARTNER_TEMPLATE = """Olá {decisor_first}! Tudo bem?

{abertura}

Sou da {sender_company}. Trabalhamos com um programa de parceiros/indicação onde você ganha comissão por cada cliente fechado a partir da sua indicação — sem mensalidade, sem trabalho operacional.

Você teria interesse em conhecer os detalhes? Posso te enviar um resumo rápido."""

_DEFAULT_DIRECT_TEMPLATE = """Olá {decisor_first}! Tudo bem?

{abertura}

Sou da {sender_company}. Pelo que vi da {nome_curto}, acredito que o que a gente entrega pode fazer sentido pra vocês.

Posso te mandar um resumo rápido pra você avaliar?"""

_DEFAULT_FOLLOWUP_1 = """Oi {decisor_first}, passando rápido pra confirmar se chegou minha mensagem. Se for o momento certo, te mando os detalhes. Tudo bem?"""

_DEFAULT_FOLLOWUP_2 = """{decisor_first}, sem querer insistir — se fizer sentido pra {nome_curto}, me avisa que te passo os detalhes."""

_DEFAULT_FOLLOWUP_3 = """{decisor_first}, última vez que te chamo aqui pra não te incomodar. Caso queira retomar no futuro, é só responder. Sucesso aí na {nome_curto}!"""


class MessagesSettings(BaseModel):
    """Templates de mensagem editáveis pelo usuário."""
    sender_name: str = ""
    sender_company: str = ""
    sender_site: str = ""
    partner_template: str = _DEFAULT_PARTNER_TEMPLATE
    direct_template: str = _DEFAULT_DIRECT_TEMPLATE
    followup_1: str = _DEFAULT_FOLLOWUP_1
    followup_2: str = _DEFAULT_FOLLOWUP_2
    followup_3: str = _DEFAULT_FOLLOWUP_3
    followup_days: list[int] = Field(default_factory=lambda: [3, 7, 15])
    use_ai_opener: bool = True   # se True, IA gera 1 frase de gancho personalizado
    generate_ab_variants: bool = True  # gera 2 versões da abertura
    use_ai_full_message: bool = False  # se True, IA escreve o CORPO INTEIRO da msg por lead (mais lento, mais personalizado)


class Settings(BaseModel):
    ai: AISettings = Field(default_factory=AISettings)
    scraping: ScrapingSettings = Field(default_factory=ScrapingSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    messages: MessagesSettings = Field(default_factory=MessagesSettings)


def _ensure_settings_file() -> None:
    if not SETTINGS_FILE.exists():
        if DEFAULT_SETTINGS_FILE.exists():
            shutil.copy(DEFAULT_SETTINGS_FILE, SETTINGS_FILE)
        else:
            SETTINGS_FILE.write_text(
                Settings().model_dump_json(indent=2), encoding="utf-8"
            )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> Settings:
    """Carrega settings.json mesclando com defaults."""
    _ensure_settings_file()
    defaults = Settings().model_dump()
    try:
        user_raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        user_raw = {}
    merged = _deep_merge(defaults, user_raw or {})
    return Settings.model_validate(merged)


def save_settings(settings: Settings) -> None:
    SETTINGS_FILE.write_text(settings.model_dump_json(indent=2), encoding="utf-8")


# Singleton lazy
_settings: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    global _settings
    if _settings is None or reload:
        _settings = load_settings()
    return _settings


def update_settings(new: Settings) -> Settings:
    global _settings
    save_settings(new)
    _settings = new
    return _settings
