"""Detecção heurística de sinais comerciais a partir do conteúdo do site.

Não substitui a IA — alimenta-a com fatos objetivos extraídos por regex,
para que a qualificação saia muito mais rica e barata.
"""
from __future__ import annotations

import re
from typing import Iterable


# --------------------------------------------------------------------------- #
# Tecnologias detectáveis pelo HTML
# --------------------------------------------------------------------------- #
TECH_SIGNATURES: dict[str, tuple[str, ...]] = {
    "WordPress": ("wp-content/", "wp-includes/", 'name="generator" content="WordPress'),
    "Wix": ("static.wixstatic.com", "wix.com"),
    "Squarespace": ("static.squarespace.com",),
    "Webflow": ("webflow.com", "data-wf-"),
    "Shopify": ("cdn.shopify.com", "shopify.com/s/"),
    "VTEX": ("vtex.com", "vtexcommercestable"),
    "Magento": ("/skin/frontend/", "Mage.Cookies"),
    "React": ("/_next/", "data-reactroot", "react-dom"),
    "Next.js": ("/_next/static/",),
    "Vue": ("vue.runtime", "data-v-"),
    "Bootstrap": ("bootstrap.min.css", "bootstrap.bundle"),
    "Tailwind": ("tailwindcss",),
    "Google Analytics": ("google-analytics.com", "gtag(", "googletagmanager.com"),
    "Meta Pixel": ("connect.facebook.net/en_US/fbevents.js", "fbq("),
    "RD Station": ("rdstation", "d335luupugsy2.cloudfront"),
    "HubSpot": ("hs-scripts.com", "js.hs-analytics.net"),
    "Mailchimp": ("list-manage.com",),
    "Hotjar": ("static.hotjar.com",),
    "Cloudflare": ("cdnjs.cloudflare.com", "challenges.cloudflare.com"),
    "Stripe": ("js.stripe.com",),
    "Mercado Pago": ("mercadopago.com",),
    "Pagar.me": ("pagar.me",),
    "Calendly": ("calendly.com",),
    "Tidio": ("tidio.co",),
    "Intercom": ("widget.intercom.io",),
}


def detect_technologies(html: str) -> list[str]:
    if not html:
        return []
    found: list[str] = []
    low = html.lower()
    for name, sigs in TECH_SIGNATURES.items():
        if any(s.lower() in low for s in sigs):
            found.append(name)
    return found


# --------------------------------------------------------------------------- #
# CNPJ (formato BR)
# --------------------------------------------------------------------------- #
_CNPJ_RE = re.compile(r"\b(\d{2}[.\s]?\d{3}[.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2})\b")


def extract_cnpj(text: str) -> str:
    if not text:
        return ""
    m = _CNPJ_RE.search(text)
    if not m:
        return ""
    digits = re.sub(r"\D", "", m.group(1))
    if len(digits) != 14:
        return ""
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


# --------------------------------------------------------------------------- #
# Sinais de compra / movimento empresarial
# --------------------------------------------------------------------------- #
BUYING_SIGNALS: dict[str, tuple[str, ...]] = {
    "Expansão": ("expansão", "expansao", "expandir", "novas unidades", "abrindo unidade",
                 "nova filial", "nova sede", "crescemos", "estamos crescendo"),
    "Contratação Executiva": ("contratamos", "novo CEO", "novo diretor", "nova liderança",
                              "junta-se ao time", "novo head", "vagas executivas"),
    "Captação / Investimento": ("captação", "captacao", "rodada", "investidor", "aporte",
                                "series a", "series b", "venture capital", "private equity",
                                "valuation", "ipo"),
    "Fusão / Aquisição": ("fusão", "fusao", "aquisição", "aquisicao", "m&a",
                          "adquiriu", "comprou a empresa", "joint venture"),
    "Reestruturação Societária": ("reestruturação societária", "holding patrimonial",
                                  "abertura de holding", "sucessão", "planejamento sucessório",
                                  "blindagem patrimonial"),
    "Franquias": ("franquia", "franchising", "abrir franquia", "modelo de franquia"),
    "Crescimento Acelerado": ("crescimento acelerado", "high growth", "scale-up",
                              "dobramos", "triplicamos", "+100%", "fastest growing"),
    "Vagas Abertas": ("trabalhe conosco", "vagas abertas", "estamos contratando",
                      "join our team", "carreiras", "we are hiring"),
    "Conteúdo Frequente": ("blog", "podcast", "webinar", "newsletter"),
    "Internacionalização": ("internacional", "global", "operações nos eua",
                            "mercado externo", "exportação"),
}


def detect_buying_signals(text: str) -> list[str]:
    if not text:
        return []
    low = text.lower()
    out: list[str] = []
    for label, words in BUYING_SIGNALS.items():
        if any(w in low for w in words):
            out.append(label)
    return out


# --------------------------------------------------------------------------- #
# Decisores (heurística simples — IA refina depois)
# --------------------------------------------------------------------------- #
DECISION_ROLES = (
    "ceo", "founder", "fundador", "cofundador", "co-fundador",
    "sócio", "socio", "sócia", "presidente", "diretor", "diretora",
    "head ", "cfo", "cto", "cmo", "coo", "owner", "proprietário",
    "proprietario", "administrador", "administradora", "gerente geral",
)

# Padrão: "Nome Sobrenome — Cargo" / "Nome Sobrenome, CEO" / "CEO: Nome Sobrenome"
_NAME_ROLE_RE = re.compile(
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+){1,3})\s*[-–—:,]\s*"
    r"(CEO|CFO|CTO|CMO|COO|Founder|Fundador|Cofundador|Co-Fundador|"
    r"Diretor[a]?|Sócio[a]?|Socio[a]?|Presidente|Owner|Propriet[áa]ri[oa]|Administrador[a]?|Head [A-Za-z]+)",
    re.UNICODE,
)
_ROLE_NAME_RE = re.compile(
    r"(CEO|CFO|CTO|CMO|COO|Founder|Fundador|Diretor[a]?|Sócio[a]?|Presidente|Head [A-Za-z]+)\s*[:\-–—]\s*"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+){1,3})",
    re.UNICODE,
)


def detect_decision_makers(text: str) -> list[dict]:
    if not text:
        return []
    found: dict[str, str] = {}
    for m in _NAME_ROLE_RE.finditer(text):
        name, role = m.group(1).strip(), m.group(2).strip()
        if name not in found:
            found[name] = role
    for m in _ROLE_NAME_RE.finditer(text):
        role, name = m.group(1).strip(), m.group(2).strip()
        if name not in found:
            found[name] = role
    out = [{"name": n, "role": r} for n, r in found.items()]
    return out[:6]


# --------------------------------------------------------------------------- #
# Estimativas de porte e tempo de mercado (heurística textual)
# --------------------------------------------------------------------------- #
_FOUNDED_RE = re.compile(
    r"(?:fundad[ao]|desde|since|criad[ao] em|estabelecid[ao] em|in business since)\s*(?:em\s*)?(\d{4})",
    re.IGNORECASE,
)
_EMPLOYEES_RE = re.compile(
    r"(?:mais de\s*)?(\d{2,5})\s*(?:colaborador|funcion[áa]ri|empregad|employees|team members|profissionais)",
    re.IGNORECASE,
)


def estimate_years_in_market(text: str, current_year: int) -> int | None:
    if not text:
        return None
    m = _FOUNDED_RE.search(text)
    if not m:
        return None
    try:
        year = int(m.group(1))
        if 1900 < year <= current_year:
            return current_year - year
    except ValueError:
        pass
    return None


def estimate_employees(text: str) -> int | None:
    if not text:
        return None
    m = _EMPLOYEES_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def classify_company_size(employees: int | None, signals: Iterable[str]) -> str:
    sig = set(signals or ())
    if employees is None:
        if "Captação / Investimento" in sig or "Fusão / Aquisição" in sig:
            return "Média/Grande"
        return "Indefinido"
    if employees < 10:
        return "Micro"
    if employees < 50:
        return "Pequena"
    if employees < 250:
        return "Média"
    return "Grande"


# --------------------------------------------------------------------------- #
# Cálculo de prioridade comercial
# --------------------------------------------------------------------------- #
def compute_priority(score: int, match_score: int, signals: Iterable[str]) -> str:
    sig = list(signals or [])
    weight = score + match_score + len(sig) * 4
    if weight >= 170 or (score >= 90 and len(sig) >= 2):
        return "maxima"
    if weight >= 130 or score >= 80:
        return "alta"
    if weight >= 90:
        return "media"
    return "baixa"


PRIORITY_LABEL = {
    "maxima": ("🔥 Prioridade Máxima", "#EF4444"),
    "alta": ("⚡ Alta Conversão", "#F59E0B"),
    "media": ("🟡 Média Prioridade", "#FBBF24"),
    "baixa": ("⚪ Baixa Prioridade", "#9CA3AF"),
}
