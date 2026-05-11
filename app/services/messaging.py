"""Serviço de mensagens: templates, abertura IA, follow-ups, hot score."""
from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from app.services.ai import AIClientError
from app.services.ai.client import _chat
from app.utils.logger import get_logger

log = get_logger("messaging")


def _decisor_first_name(lead: dict[str, Any]) -> str:
    dms = lead.get("decision_makers") or []
    if isinstance(dms, list) and dms:
        name = (dms[0].get("name") or "").strip()
        if name:
            return name.split()[0]
    return ""


def _company_short_name(lead: dict[str, Any]) -> str:
    """Pega só a parte 'comercial' do nome da empresa, sem LTDA/ME/razão social."""
    raw = (lead.get("name") or "").strip()
    if not raw:
        return ""
    # Remove sufixos comuns
    cleaned = re.sub(
        r"\b(ltda|me|eireli|s\.?a\.?|epp|mei|cia|comercio|comércio|servicos|serviços|"
        r"industria|indústria|representacoes|representações)\b\.?",
        "", raw, flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[-–|/]+.*$", "", cleaned).strip(" .,-")
    # Pega 1ª ou 2 primeiras palavras significativas
    parts = [p for p in cleaned.split() if len(p) > 1]
    if not parts:
        return raw.split()[0] if raw.split() else raw
    return " ".join(parts[:2])


def _placeholders(lead: dict[str, Any], opener: str = "") -> dict[str, str]:
    decisor = _decisor_first_name(lead)
    company_short = _company_short_name(lead)
    # Se não tem decisor identificado, usa nome curto da empresa
    saudacao_alvo = decisor or company_short or "tudo bem"
    s = get_settings().messages
    return {
        "nome": (lead.get("name") or "sua empresa").strip(),
        "nome_curto": company_short or (lead.get("name") or "").strip(),
        "saudacao": saudacao_alvo,
        "cidade": (lead.get("city") or "").strip(),
        "uf": (lead.get("state") or "").strip(),
        "nicho": (lead.get("niche") or "").strip(),
        "site": (lead.get("website") or "").strip(),
        "telefone": (lead.get("phone") or "").strip(),
        "email": (lead.get("email") or "").strip(),
        "decisor": decisor or company_short,
        "decisor_first": decisor or company_short,
        "abertura": opener or "",
        "sender_name": (s.sender_name or "").strip(),
        "sender_company": (s.sender_company or "").strip(),
        "sender_site": (s.sender_site or "").strip(),
    }


def render_template(template: str, lead: dict[str, Any], opener: str = "") -> str:
    """Substitui placeholders {nome}, {cidade}, {decisor_first}, {abertura}, etc."""
    out = template or ""
    ph = _placeholders(lead, opener=opener)
    for k, v in ph.items():
        out = out.replace("{" + k + "}", v)
    # Limpa duplas quebras de linha quando abertura está vazia
    out = re.sub(r"\n\n\n+", "\n\n", out).strip()
    return out


def detect_tone(lead: dict[str, Any]) -> str:
    """Decide se a mensagem deve ser 'formal' ou 'casual'."""
    employees = lead.get("employees_estimate") or 0
    years = lead.get("years_in_market") or 0
    reviews = lead.get("google_reviews") or 0
    rating = float(lead.get("google_rating") or 0)
    big_signals = (employees and employees >= 10) or years >= 8 or reviews >= 100
    if big_signals or (rating >= 4.5 and reviews >= 30):
        return "formal"
    return "casual"


def compute_hot_score(lead: dict[str, Any]) -> int:
    """0-100 — quão 'quente' é o lead para abordar AGORA."""
    score = 0
    if lead.get("phone") or lead.get("whatsapp"):
        score += 25
    if lead.get("email"):
        score += 15
    if lead.get("instagram"):
        score += 5
    if lead.get("website"):
        score += 10
    sigs = lead.get("buying_signals") or []
    if isinstance(sigs, list):
        score += min(20, len(sigs) * 5)
    rating = float(lead.get("google_rating") or 0)
    if rating >= 4.5:
        score += 10
    elif rating >= 4.0:
        score += 5
    if (lead.get("decision_makers") or []):
        score += 10
    match = int(lead.get("match_score") or 0)
    score += int(match * 0.05)
    return max(0, min(100, score))


def has_minimum_contact(lead: dict[str, Any]) -> bool:
    """B3: só salvar lead se tiver telefone, email, whatsapp ou instagram."""
    return bool(
        (lead.get("phone") or "").strip()
        or (lead.get("whatsapp") or "").strip()
        or (lead.get("email") or "").strip()
        or (lead.get("instagram") or "").strip()
    )


# ---------------------------------------------------------------------------
# IA — gera 1 frase de gancho personalizado
# ---------------------------------------------------------------------------
_OPENER_SYSTEM = (
    "Você é um SDR brasileiro experiente. Sua tarefa é gerar APENAS UMA frase "
    "de abertura curta (no máximo 22 palavras) para uma mensagem comercial. "
    "A frase deve mencionar algo CONCRETO e VERIFICÁVEL do lead (nome, cidade, "
    "nota Google, anos de mercado, nicho, sinal detectado), em tom natural, "
    "como se você tivesse pesquisado a empresa. NUNCA use clichês como "
    "'parabéns pelo trabalho' ou 'admiro muito o que vocês fazem'. "
    "Responda APENAS com JSON: {\"opener\": \"frase\", \"opener_b\": \"variante alternativa\"}"
)


def generate_opener(lead: dict[str, Any], mode: str, tone: str) -> tuple[str, str]:
    """Gera (abertura_a, abertura_b) ou ('', '') se IA falhar."""
    s = get_settings()
    if not s.messages.use_ai_opener:
        return "", ""
    sigs = ", ".join(lead.get("buying_signals") or []) or "—"
    dms = lead.get("decision_makers") or []
    dm_str = ", ".join(f"{d.get('name','')} ({d.get('role','')})" for d in dms) or "—"
    prompt = f"""LEAD:
- Nome: {lead.get('name','')}
- Nicho: {lead.get('niche','')}
- Cidade/UF: {lead.get('city','')}/{lead.get('state','')}
- Site: {lead.get('website','')}
- Anos de mercado: {lead.get('years_in_market') or '—'}
- Funcionários: {lead.get('employees_estimate') or '—'}
- Google: {lead.get('google_rating') or '—'} ({lead.get('google_reviews') or 0} reviews)
- Sinais detectados: {sigs}
- Decisores: {dm_str}
- Trecho do site: {(lead.get('site_excerpt') or '')[:600]}

MODO: {"PARCEIRO" if mode == "partners" else "CLIENTE DIRETO"}
TOM: {tone}

Gere a abertura. Retorne JSON {{"opener":"...","opener_b":"..."}}."""
    try:
        out = _chat(prompt, system=_OPENER_SYSTEM, json_mode=True)
        a = (out.get("opener") or "").strip().strip('"')
        b = (out.get("opener_b") or "").strip().strip('"')
        return a, b
    except AIClientError as e:
        log.warning(f"Opener IA falhou: {e}")
        return "", ""
    except Exception as e:  # noqa: BLE001
        log.debug(f"Opener IA erro: {e}")
        return "", ""


# ---------------------------------------------------------------------------
# Pública: enrich_messages — popula message_a/b a partir do template
# ---------------------------------------------------------------------------
def build_messages_for_lead(lead: dict[str, Any], use_ai: bool = False) -> dict[str, str]:
    """Retorna dict com message_a, message_b, message_opener, message_tone, hot_score.

    Por padrão NÃO chama IA — só renderiza o template (rápido, ~ms).
    Passe use_ai=True para gerar abertura personalizada via IA (lento, ~5-10s).
    Se settings.messages.use_ai_full_message=True E use_ai=True, gera o
    CORPO INTEIRO da mensagem via IA usando o ICP do usuário + dados do lead.
    """
    s = get_settings().messages
    mode = lead.get("prospection_mode") or "direct_sale"
    template = s.partner_template if mode == "partners" else s.direct_template
    tone = detect_tone(lead)

    # Modo IA full: gera mensagem inteira personalizada por lead
    if use_ai and getattr(s, "use_ai_full_message", False):
        try:
            from app.services import user_icp as _icp_mod
            icp = _icp_mod.load()
        except Exception:
            icp = {}
        full = generate_full_message(lead, icp, mode=mode)
        if full:
            return {
                "message_a": full,
                "message_b": "",
                "message_opener": "",
                "message_tone": tone,
                "hot_score": compute_hot_score(lead),
            }
        # se falhar, cai no fluxo de template

    if use_ai and s.use_ai_opener:
        opener_a, opener_b = generate_opener(lead, mode, tone)
    else:
        opener_a, opener_b = "", ""
    msg_a = render_template(template, lead, opener=opener_a)
    msg_b = ""
    if use_ai and s.generate_ab_variants and (opener_b or opener_a):
        msg_b = render_template(template, lead, opener=opener_b or opener_a)
    return {
        "message_a": msg_a,
        "message_b": msg_b,
        "message_opener": opener_a,
        "message_tone": tone,
        "hot_score": compute_hot_score(lead),
    }


def regenerate_ai_messages(lead: dict[str, Any]) -> dict[str, str]:
    """Versão sob demanda: chama IA. Use no botão 'Regenerar' do detalhe."""
    return build_messages_for_lead(lead, use_ai=True)


def followup_message(lead: dict[str, Any], step: int) -> str:
    """Renderiza follow-up D+3, D+7 ou D+15."""
    s = get_settings().messages
    template = {1: s.followup_1, 2: s.followup_2, 3: s.followup_3}.get(step, "")
    return render_template(template, lead)


# ---------------------------------------------------------------------------
# IA — gera templates personalizados a partir do ICP do usuário (onboarding)
# ---------------------------------------------------------------------------
_TEMPLATE_GEN_SYSTEM = (
    "Você é um copywriter de vendas B2B brasileiro. Sua tarefa é escrever "
    "TEMPLATES de mensagem WhatsApp para prospecção, em português do Brasil, "
    "tom natural, sem jargão. Os templates devem usar placeholders entre chaves: "
    "{decisor_first} (primeiro nome), {nome} (nome da empresa do lead), "
    "{nome_curto} (nome curto), {cidade}, {abertura} (frase de gancho gerada por outra IA). "
    "NÃO use clichês como 'parabéns pelo trabalho'. "
    "Mensagens curtas (8-15 linhas), com CTA claro no final. "
    "Responda APENAS com JSON: {\"direct\":\"...\",\"partner\":\"...\","
    "\"followup_1\":\"...\",\"followup_2\":\"...\",\"followup_3\":\"...\"}"
)


def generate_templates_from_icp(icp: dict[str, Any]) -> dict[str, str]:
    """A partir do ICP do usuário, gera templates personalizados via IA.

    Retorna {direct, partner, followup_1, followup_2, followup_3} ou {} se falhar.
    """
    company = (icp.get("company_name") or "").strip()
    site = (icp.get("website") or "").strip()
    pitch = (icp.get("business_summary") or "").strip()
    ideal = (icp.get("ideal_client") or "").strip()
    diff = (icp.get("differentials") or "").strip()
    ticket = (icp.get("avg_ticket") or "").strip()
    cta = (icp.get("cta") or "").strip()
    has_partner = bool(icp.get("partner_program"))
    partner_terms = (icp.get("partner_terms") or "").strip()

    prompt = f"""MEU NEGÓCIO:
- Empresa: {company}
- Site: {site}
- O que vendemos: {pitch}
- Cliente ideal: {ideal}
- Diferenciais: {diff or '—'}
- Ticket médio: {ticket or '—'}
- Chamada para ação preferida: {cta or 'pedir uma conversa rápida'}
- Tem programa de parceiros/indicação? {"Sim — " + partner_terms if has_partner else "Não"}

Gere 5 textos:
1. "direct" — mensagem inicial pra prospecção DIRETA (vender pro próprio lead).
2. "partner" — mensagem pra convidar o lead a ser PARCEIRO/indicador {"(use os termos: " + partner_terms + ")" if has_partner and partner_terms else "(se não tiver programa, escreva igual ao direct)"}.
3. "followup_1" — D+3, leve, lembrete.
4. "followup_2" — D+7, agrega valor (case ou benefício).
5. "followup_3" — D+15, encerramento educado.

Use {{decisor_first}}, {{nome}}, {{abertura}} como placeholders.
Comece SEMPRE com "Olá {{decisor_first}}! Tudo bem?" nos 2 primeiros, e "{{decisor_first}}," nos follow-ups.
Após a saudação, deixe uma linha em branco e {{abertura}} (só nos 2 primeiros).
Retorne JSON puro."""

    try:
        out = _chat(prompt, system=_TEMPLATE_GEN_SYSTEM, json_mode=True)
        result = {}
        for k in ("direct", "partner", "followup_1", "followup_2", "followup_3"):
            v = (out.get(k) or "").strip()
            if v:
                result[k] = v
        return result
    except AIClientError as e:
        log.warning(f"Template gen IA falhou: {e}")
        return {}
    except Exception as e:  # noqa: BLE001
        log.debug(f"Template gen erro: {e}")
        return {}


# ---------------------------------------------------------------------------
# IA — gera mensagem COMPLETA personalizada por lead (corpo todo)
# ---------------------------------------------------------------------------
_FULL_MSG_SYSTEM = (
    "Você é um SDR brasileiro experiente escrevendo mensagens WhatsApp 1-a-1 "
    "para prospecção B2B. Cada mensagem deve ser ÚNICA, baseada no site e "
    "contexto do lead, e claramente conectada ao que o vendedor oferece. "
    "Tom natural, sem clichês, sem 'parabéns', sem 'admiro o trabalho'. "
    "8-14 linhas. Saudação curta, gancho concreto do site/contexto, "
    "1-2 linhas explicando o que o vendedor faz e por que faz sentido pra ESSE lead, "
    "CTA claro no final. "
    "Responda APENAS com JSON: {\"message\":\"texto completo\"}"
)


def generate_full_message(lead: dict[str, Any], icp: dict[str, Any], mode: str = "direct_sale") -> str:
    """Gera o CORPO INTEIRO da mensagem usando IA + ICP do usuário + dados do lead."""
    company = (icp.get("company_name") or "").strip()
    site = (icp.get("website") or "").strip()
    pitch = (icp.get("business_summary") or "").strip()
    diff = (icp.get("differentials") or "").strip()
    ticket = (icp.get("avg_ticket") or "").strip()
    cta = (icp.get("cta") or "uma conversa rápida").strip()
    partner_terms = (icp.get("partner_terms") or "").strip()

    decisor = _decisor_first_name(lead) or _company_short_name(lead) or "tudo bem"
    sigs = ", ".join(lead.get("buying_signals") or []) or "—"
    excerpt = (lead.get("site_excerpt") or "")[:800]

    prompt = f"""VENDEDOR (eu):
- Empresa: {company} ({site})
- O que vendemos: {pitch}
- Diferenciais: {diff or '—'}
- Ticket médio: {ticket or '—'}
- CTA preferido: {cta}
{"- Programa de parceiros: " + partner_terms if mode == "partners" and partner_terms else ""}

LEAD:
- Empresa: {lead.get('name','')}
- Nicho: {lead.get('niche','')}
- Cidade/UF: {lead.get('city','')}/{lead.get('state','')}
- Site: {lead.get('website','')}
- Decisor: {decisor}
- Sinais: {sigs}
- Trecho do site:
\"\"\"
{excerpt}
\"\"\"

MODO: {"PARCEIRO/INDICADOR" if mode == "partners" else "VENDA DIRETA"}

Escreva a mensagem WhatsApp final (sem placeholders, já com o nome do decisor e referência concreta do site). JSON: {{"message":"..."}}"""
    try:
        out = _chat(prompt, system=_FULL_MSG_SYSTEM, json_mode=True)
        return (out.get("message") or "").strip()
    except AIClientError as e:
        log.warning(f"Full msg IA falhou: {e}")
        return ""
    except Exception as e:  # noqa: BLE001
        log.debug(f"Full msg erro: {e}")
        return ""

