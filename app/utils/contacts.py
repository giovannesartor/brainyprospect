"""Extração e validação de contatos a partir de texto/HTML."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import phonenumbers
from email_validator import EmailNotValidError, validate_email

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)
PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.\-]?)?(\(?\d{2,4}\)?[\s.\-]?)?\d{3,5}[\s.\-]?\d{3,5}",
)
WHATSAPP_RE = re.compile(
    r"(?:wa\.me|api\.whatsapp\.com/send)\??[^\s\"']*",
    re.IGNORECASE,
)
INSTAGRAM_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?",
    re.IGNORECASE,
)
LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9_\-%]+)/?",
    re.IGNORECASE,
)


def extract_emails(text: str) -> list[str]:
    found = set()
    for raw in EMAIL_RE.findall(text or ""):
        try:
            v = validate_email(raw, check_deliverability=False)
            found.add(v.normalized.lower())
        except EmailNotValidError:
            continue
    # filtra placeholders comuns
    blacklist = ("example.com", "email.com", "domain.com", "sentry.io", "wixpress.com")
    return sorted(e for e in found if not any(b in e for b in blacklist))


def extract_phones(text: str, region: str = "BR") -> list[str]:
    found: set[str] = set()
    for match in phonenumbers.PhoneNumberMatcher(text or "", region):
        n = match.number
        if phonenumbers.is_possible_number(n) and phonenumbers.is_valid_number(n):
            found.add(phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164))
    return sorted(found)


def extract_whatsapp(text: str) -> list[str]:
    return sorted(set(WHATSAPP_RE.findall(text or "")))


def extract_whatsapp_numbers(text: str) -> list[str]:
    """Extrai NÚMEROS E.164 a partir de URLs wa.me e api.whatsapp.com/send?phone=...

    Esses números são muito mais confiáveis que telefones soltos no texto,
    porque foram explicitamente cadastrados como WhatsApp pelo dono do site.
    """
    found: set[str] = set()
    if not text:
        return []
    # wa.me/55119...
    for m in re.finditer(r"wa\.me/(?:\+?)([0-9]{8,15})", text, re.IGNORECASE):
        digits = m.group(1)
        if len(digits) >= 10:
            num = digits if digits.startswith("55") else ("55" + digits if len(digits) <= 11 else digits)
            found.add("+" + num)
    # api.whatsapp.com/send?phone=55119...
    for m in re.finditer(
        r"api\.whatsapp\.com/send[^\s\"']*?phone=(?:\+?)([0-9]{8,15})",
        text, re.IGNORECASE,
    ):
        digits = m.group(1)
        if len(digits) >= 10:
            num = digits if digits.startswith("55") else ("55" + digits if len(digits) <= 11 else digits)
            found.add("+" + num)
    # valida com phonenumbers
    valid: list[str] = []
    for raw in found:
        try:
            n = phonenumbers.parse(raw, "BR")
            if phonenumbers.is_valid_number(n):
                valid.append(phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164))
        except Exception:
            continue
    return sorted(set(valid))


def pick_best_phone(phones: list[str], *, prefer_mobile: bool = True) -> str:
    """Escolhe o melhor telefone de uma lista E.164.

    Prioridade: móvel BR (DDD + 9xxxx-xxxx) > fixo BR > qualquer.
    """
    if not phones:
        return ""
    mobiles: list[str] = []
    fixed: list[str] = []
    others: list[str] = []
    for p in phones:
        try:
            n = phonenumbers.parse(p, "BR")
            if not phonenumbers.is_valid_number(n):
                continue
            kind = phonenumbers.number_type(n)
            if kind == phonenumbers.PhoneNumberType.MOBILE:
                mobiles.append(p)
            elif kind == phonenumbers.PhoneNumberType.FIXED_LINE:
                fixed.append(p)
            elif kind == phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE:
                # heurística BR: 11 dígitos após país + 9 logo após DDD = móvel
                national = phonenumbers.format_number(
                    n, phonenumbers.PhoneNumberFormat.NATIONAL,
                )
                digits = re.sub(r"\D+", "", national)
                if len(digits) == 11 and digits[2] == "9":
                    mobiles.append(p)
                else:
                    fixed.append(p)
            else:
                others.append(p)
        except Exception:
            others.append(p)
    if prefer_mobile and mobiles:
        return mobiles[0]
    return (mobiles or fixed or others or phones)[0]


def extract_instagram(text: str) -> list[str]:
    return sorted({"https://instagram.com/" + m for m in INSTAGRAM_RE.findall(text or "")})


def extract_linkedin(text: str) -> list[str]:
    return sorted({"https://linkedin.com/company/" + m for m in LINKEDIN_RE.findall(text or "")})


def domain_of(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""
