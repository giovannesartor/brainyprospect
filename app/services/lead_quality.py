"""Filtros de qualidade dos leads (B6-B10).

Aplicados em sequência sobre `LeadDraft` para descartar lixo ANTES de salvar.
Cada função retorna (keep: bool, reason: str). Reason é usado no log.
"""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

from app.services.ai import AIClientError
from app.services.ai.client import _chat
from app.utils.logger import get_logger

log = get_logger("quality")


# ---------------------------------------------------------------------------
# B6 — Marcas globais / muito grandes (impossíveis de prospectar como cliente)
# ---------------------------------------------------------------------------
_KNOWN_BRANDS = {
    # Tech global
    "google", "microsoft", "apple", "amazon", "meta", "facebook", "instagram",
    "whatsapp", "youtube", "twitter", "linkedin", "tiktok", "spotify", "netflix",
    "uber", "airbnb", "tesla", "samsung", "huawei", "xiaomi", "sony", "intel",
    "nvidia", "amd", "ibm", "oracle", "salesforce", "adobe", "shopify", "ebay",
    "alibaba", "tencent", "baidu", "yahoo", "paypal", "stripe", "openai",
    # Varejo BR grandes
    "magazine luiza", "magalu", "casas bahia", "ponto frio", "americanas",
    "submarino", "extra", "carrefour", "pao de acucar", "pão de açúcar",
    "assai", "atacadão", "atacadao", "walmart", "renner", "c&a", "riachuelo",
    "marisa", "havaianas", "natura", "boticário", "boticario", "o boticário",
    "o boticario", "avon", "eudora",
    # Comida/Apps BR
    "ifood", "rappi", "uber eats", "99", "99app", "mercadolivre", "mercado livre",
    "olx", "amazon brasil", "kabum", "magazine voce", "americanas marketplace",
    # Bancos
    "itau", "itaú", "bradesco", "santander", "banco do brasil", "caixa",
    "nubank", "inter", "c6 bank", "btg", "xp", "btg pactual",
    # Telecom
    "vivo", "claro", "tim", "oi", "algar", "sercomtel",
    # Mídia
    "globo", "sbt", "record", "band", "rede tv", "globoplay",
    # Educação/Editoras
    "saraiva", "fnac", "cultura", "kroton", "anhanguera", "estácio", "estacio",
    "yduqs", "uol", "terra", "ig", "r7", "msn",
    # Moda global
    "nike", "adidas", "puma", "zara", "h&m", "uniqlo", "gap", "calvin klein",
    "tommy hilfiger", "louis vuitton", "gucci", "prada", "channel", "chanel",
    # Auto
    "toyota", "honda", "ford", "chevrolet", "fiat", "volkswagen", "vw",
    "renault", "hyundai", "nissan", "bmw", "mercedes", "audi", "jeep",
    # Comida fast-food
    "mcdonald", "mcdonalds", "burger king", "subway", "kfc", "starbucks",
    "coca cola", "coca-cola", "pepsi", "ambev",
    # ONGs / governo
    "sesi", "senai", "sebrae", "sesc", "senac", "fiesp", "ciesp",
    "petrobras", "vale", "embraer", "eletrobras", "correios", "infraero",
}


def _normalize_name(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"\b(ltda|me|eireli|s\.?a\.?|epp|mei|cia)\b\.?", "", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_known_brand(name: str) -> bool:
    """B6: nome bate com marca global/grande conhecida."""
    n = _normalize_name(name)
    if not n:
        return False
    if n in _KNOWN_BRANDS:
        return True
    # match por palavra inteira (evita 'natura' achando 'natural')
    tokens = set(n.split())
    for brand in _KNOWN_BRANDS:
        b_tokens = brand.split()
        if all(bt in tokens for bt in b_tokens) and len(b_tokens) >= 1:
            # exige que TODAS as palavras da marca estejam no nome E
            # que o nome não tenha muito mais que isso (evita falsos positivos)
            if len(tokens) <= len(b_tokens) + 2:
                return True
    return False


# ---------------------------------------------------------------------------
# B7 — Site é da empresa? (domínio precisa conter algum token do nome)
# ---------------------------------------------------------------------------
_SITE_GENERIC_TOKENS = {
    "com", "br", "www", "net", "org", "site", "shop", "loja", "online",
    "oficial", "empresa", "company", "co", "ltda", "me", "sa",
}


def site_matches_name(name: str, website: str) -> bool:
    """B7: pelo menos 1 token significativo do nome aparece no domínio.

    Retorna True se site PROVÁVEL ser da empresa, False se suspeito.
    Se não houver site, retorna True (não bloqueia).
    """
    if not website:
        return True
    try:
        host = (urlparse(website if "://" in website else "https://" + website).hostname or "").lower()
    except Exception:
        return True
    if not host:
        return True
    host = host.removeprefix("www.")
    host_naked = re.sub(r"\.(com|com\.br|net|org|io|co|me|app)$", "", host)
    host_tokens = set(re.split(r"[.\-_]+", host_naked))
    name_tokens = set(_normalize_name(name).split()) - _SITE_GENERIC_TOKENS
    if not name_tokens:
        return True
    # Match: qualquer token do nome (>=4 chars) é substring do host_naked
    flat = host_naked.replace(".", "").replace("-", "").replace("_", "")
    for t in name_tokens:
        if len(t) >= 4 and (t in flat or t in host_tokens):
            return True
    return False


# ---------------------------------------------------------------------------
# B8 — Mínimo de sinais de contato (mais rigoroso que has_minimum_contact)
# ---------------------------------------------------------------------------
_PUBLIC_EMAIL_DOMS = {
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br",
    "uol.com.br", "bol.com.br", "ig.com.br", "terra.com.br", "live.com",
    "icloud.com", "msn.com", "globo.com",
}


def is_corporate_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    dom = email.split("@", 1)[1].strip().lower()
    return dom not in _PUBLIC_EMAIL_DOMS


def has_strong_contact(lead: dict) -> bool:
    """B8: precisa de telefone OU whatsapp + (email corp OU site OU instagram)."""
    has_phone = bool((lead.get("phone") or "").strip()
                     or (lead.get("whatsapp") or "").strip())
    has_other = (
        is_corporate_email(lead.get("email") or "")
        or bool((lead.get("website") or "").strip())
        or bool((lead.get("instagram") or "").strip())
    )
    return has_phone and has_other


# ---------------------------------------------------------------------------
# B9 — Nichos genéricos
# ---------------------------------------------------------------------------
_GENERIC_NICHES = {
    "", "—", "-", "diversos", "geral", "outros", "outro", "varios", "vários",
    "n/a", "na", "none", "null", "indefinido", "sem categoria", "sem nicho",
}


def is_generic_niche(niche: str) -> bool:
    return (niche or "").strip().lower() in _GENERIC_NICHES


# ---------------------------------------------------------------------------
# Aplicação combinada (B6+B7+B8+B9) — síncrona, rápida, antes de salvar
# ---------------------------------------------------------------------------
def passes_local_filters(lead: dict) -> tuple[bool, str]:
    """Retorna (passa, motivo_se_descartado)."""
    name = (lead.get("name") or "").strip()
    if not name:
        return False, "sem nome"
    if is_known_brand(name):
        return False, f"marca conhecida: {name[:60]}"
    if is_generic_niche(lead.get("niche") or ""):
        return False, "nicho genérico"
    if not site_matches_name(name, lead.get("website") or ""):
        return False, f"site não bate com nome ({lead.get('website','')[:60]})"
    if not has_strong_contact(lead):
        return False, "contato fraco (precisa telefone + (email corp / site / IG))"
    return True, ""


# ---------------------------------------------------------------------------
# B10 — IA classifica em batch (10 leads/call) → keep|skip + razão
# ---------------------------------------------------------------------------
_CLASSIFY_SYSTEM = (
    "Você é um SDR sênior brasileiro decidindo quais leads valem o tempo do time. "
    "Para CADA lead, decida 'keep' (vale prospectar) ou 'skip' (lixo, marca grande "
    "demais, dado errado, irrelevante). Seja RIGOROSO — prefira descartar dúvidas. "
    "Responda APENAS JSON: {\"results\": [{\"id\": 1, \"decision\": \"keep|skip\", "
    "\"reason\": \"até 12 palavras\"}, ...]}"
)


def _format_lead_for_classify(idx: int, lead: dict) -> str:
    sigs = ", ".join(lead.get("buying_signals") or []) or "—"
    return (
        f"#{idx} | {lead.get('name','')[:80]} | {lead.get('niche','')} "
        f"| {lead.get('city','')}/{lead.get('state','')} "
        f"| site={lead.get('website','')[:60] or '—'} "
        f"| tel={lead.get('phone','') or '—'} "
        f"| wa={lead.get('whatsapp','') or '—'} "
        f"| email={lead.get('email','') or '—'} "
        f"| sinais={sigs}"
    )


def classify_batch_with_ai(
    leads: list[dict], *, business_summary: str = "", batch_size: int = 10,
) -> dict[int, tuple[str, str]]:
    """B10: classifica em lotes de N. Retorna {idx_original: (decision, reason)}.

    Falha de IA = considera todos como 'keep' (não bloqueia).
    """
    out: dict[int, tuple[str, str]] = {}
    if not leads:
        return out
    for start in range(0, len(leads), batch_size):
        chunk = leads[start:start + batch_size]
        listing = "\n".join(
            _format_lead_for_classify(i, ld) for i, ld in enumerate(chunk, 1)
        )
        prompt = (
            (f"NEGÓCIO: {business_summary[:400]}\n\n" if business_summary else "")
            + f"LEADS ({len(chunk)}):\n{listing}\n\n"
            "Decida keep/skip para cada um. JSON conforme instrução."
        )
        try:
            resp = _chat(prompt, system=_CLASSIFY_SYSTEM, json_mode=True)
            results = resp.get("results") or []
            seen_local: set[int] = set()
            for r in results:
                try:
                    local_id = int(r.get("id") or 0)
                except Exception:
                    continue
                if local_id < 1 or local_id > len(chunk):
                    continue
                seen_local.add(local_id)
                decision = (r.get("decision") or "keep").strip().lower()
                if decision not in ("keep", "skip"):
                    decision = "keep"
                reason = (r.get("reason") or "").strip()[:120]
                out[start + local_id - 1] = (decision, reason)
            # qualquer lead não retornado pela IA -> keep (não bloqueia)
            for i in range(1, len(chunk) + 1):
                if i not in seen_local:
                    out[start + i - 1] = ("keep", "sem decisão IA")
        except AIClientError as e:
            log.warning(f"IA classify falhou: {e} — mantendo todos do lote")
            for i in range(len(chunk)):
                out[start + i] = ("keep", "ia indisponível")
        except Exception as e:  # noqa: BLE001
            log.debug(f"classify erro: {e}")
            for i in range(len(chunk)):
                out[start + i] = ("keep", "ia erro")
    return out


def filter_with_ai(
    leads: list[dict], *, business_summary: str = "", batch_size: int = 10,
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Aplica B10. Retorna (kept_leads, [(name, reason)]_descartados)."""
    decisions = classify_batch_with_ai(
        leads, business_summary=business_summary, batch_size=batch_size,
    )
    kept: list[dict] = []
    dropped: list[tuple[str, str]] = []
    for i, ld in enumerate(leads):
        dec, reason = decisions.get(i, ("keep", ""))
        if dec == "skip":
            dropped.append((ld.get("name", "?"), reason or "ia: skip"))
        else:
            kept.append(ld)
    return kept, dropped
