"""Orquestra: site -> análise IA -> busca de leads -> enriquecimento -> qualificação.

Suporta MODOS de prospecção:
- direct_sale  : busca clientes finais
- partners     : busca parceiros/multiplicadores
- both         : roda os dois e classifica/separa
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlparse

from app.database import LeadRepository, SearchRepository
from app.database.extra_repositories import AnalysisCacheRepository
from app.models import ICPProfile, LeadDraft
from app.scrapers import scrape_site, search_bing, search_duckduckgo, search_google_maps
from app.services.ai import AIClientError, analyze_site, generate_product, qualify_lead
from app.services.contact_enricher import enrich_from_website
from app.services.intelligence import compute_priority
from app.services.lead_quality import filter_with_ai, passes_local_filters
from app.services.messaging import build_messages_for_lead, has_minimum_contact
from app.utils.logger import get_logger

log = get_logger("hunter")

ProgressFn = Callable[[str, int], None]

# Limite máximo de leads enriquecidos por nicho (P6)
_MAX_ENRICH_PER_NICHE = 30
# Threads paralelas para enriquecimento (P2)
_ENRICH_WORKERS = 8


@dataclass
class HuntRequest:
    source_input: str = ""
    is_website: bool = False
    manual_niches: list[str] = field(default_factory=list)
    city: str = ""
    state: str = ""
    country: str = "Brasil"
    max_per_niche: int = 15
    use_ai_qualification: bool = True
    # Estratégia comercial
    mode: str = "direct_sale"   # 'direct_sale' | 'partners' | 'both'
    # Produtos selecionados pelo usuário (após Analisar Site).
    # Cada item: {
    #   "name": str, "mode": "direct_sale"|"partners"|"both",
    #   "direct_keywords": [str], "direct_clients": [str],
    #   "partner_keywords": [str], "partner_segments": [str],
    # }
    # Quando preenchido, a busca é feita POR PRODUTO+MODO em vez do modo global.
    selected_products: list[dict] = field(default_factory=list)
    # ICP previamente analisado (evita re-analisar quando vem do fluxo "Analisar Site").
    preloaded_icp: dict | None = None
    preloaded_summary: str = ""


@dataclass
class HuntResult:
    search_id: int
    icp: ICPProfile
    leads: list[LeadDraft]
    direct_count: int = 0
    partners_count: int = 0


def _noop(_msg: str, _pct: int) -> None:
    pass


# Domínios e padrões que indicam matéria/blog/agregador, não empresa real.
_BING_BLOCK_HOSTS = (
    "wikipedia.org", "youtube.com", "youtu.be", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "linkedin.com", "tiktok.com", "pinterest.",
    "reddit.com", "medium.com", "quora.com", "g1.globo.com", "globo.com",
    "uol.com.br", "terra.com.br", "ig.com.br", "r7.com", "estadao.com.br",
    "folha.uol.com.br", "valor.globo.com", "exame.com", "infomoney.com.br",
    "veja.abril.com.br", "istoedinheiro.com.br", "época.globo.com",
    "yahoo.com", "msn.com", "bing.com", "google.com",
    "amazon.com", "amazon.com.br", "mercadolivre.com.br", "olx.com.br",
    "reclameaqui.com.br", "tripadvisor.", "booking.com",
    "gov.br", ".gov.", "jusbrasil.com.br", "sympla.com.br", "eventbrite.",
    "slideshare.net", "scribd.com", "academia.edu",
)
_BING_BLOCK_PATH_TOKENS = (
    "/blog", "/noticia", "/notícia", "/news/", "/artigo", "/post/",
    "/wiki/", "/category/", "/tag/", "/forum", "/topic/",
)

# Domínios "portal/agregador" disfarçados — se o host for SUBDOMÍNIO, descarta.
_PORTAL_PARENTS = (
    "wordpress.com", "blogspot.com", "medium.com", "wix.com", "wixsite.com",
    "weebly.com", "webnode.com", "site123.me", "tumblr.com",
)


def _is_portal_subdomain(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        for parent in _PORTAL_PARENTS:
            if host.endswith("." + parent):
                return True
        return False
    except Exception:  # noqa: BLE001
        return False


def _looks_like_article_title(title: str) -> bool:
    """B1: descarta títulos com 4+ palavras maiúsculas seguidas (manchete)."""
    if not title:
        return False
    words = title.split()
    streak = 0
    for w in words:
        if w[:1].isupper() and len(w) > 2 and w.isalpha():
            streak += 1
            if streak >= 4:
                return True
        else:
            streak = 0
    # heurísticas extras de manchete
    low = title.lower()
    if any(tok in low for tok in (
        "como ", "por que ", "veja ", "saiba ", "confira ", "tudo sobre ",
        "guia completo", "passo a passo", "melhores ", " ranking ", " top ",
    )):
        return True
    return False


def _filter_bing_results(results: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in results or []:
        url = (r.get("url") or "").lower()
        title = (r.get("title") or "").strip()
        if not url:
            continue
        if any(b in url for b in _BING_BLOCK_HOSTS):
            continue
        if any(tok in url for tok in _BING_BLOCK_PATH_TOKENS):
            continue
        if url.endswith((".pdf", ".doc", ".docx", ".ppt", ".pptx")):
            continue
        if _is_portal_subdomain(url):
            continue
        if _looks_like_article_title(title):
            continue
        out.append(r)
    return out


def _build_query(niche: str, req: HuntRequest) -> str:
    parts = [niche]
    if req.city:
        parts.append("em " + req.city)
    if req.state and req.state not in (req.city, ""):
        parts.append(req.state)
    return " ".join(parts).strip()


def _niches_for_mode(icp: ICPProfile, mode: str, manual: list[str]) -> list[str]:
    if manual:
        return list(dict.fromkeys(manual))[:8]
    if mode == "partners":
        base = icp.partner_keywords or icp.partner_segments
    else:
        base = icp.direct_keywords or icp.direct_clients
    if not base:
        base = icp.keywords or icp.ideal_clients
    return [n for n in dict.fromkeys(base) if n][:8]


def _default_tag_for_mode(mode: str) -> str:
    return "Parceiro" if mode == "partners" else "Cliente Direto"


def _niches_from_product(product: dict, mode: str) -> list[str]:
    """Extrai nichos de um produto específico para o modo dado."""
    if mode == "partners":
        base = product.get("partner_keywords") or product.get("partner_segments") or []
    else:
        base = product.get("direct_keywords") or product.get("direct_clients") or []
    return [n for n in dict.fromkeys(base) if n][:8]


def _run_for_mode(*, req: HuntRequest, icp: ICPProfile, business_summary: str,
                  mode: str, progress: ProgressFn,
                  pct_offset: int, pct_budget: int,
                  niches_override: list[str] | None = None,
                  label_suffix: str = "") -> list[LeadDraft]:
    if niches_override is not None:
        niches = [n for n in dict.fromkeys(niches_override) if n][:8]
    else:
        niches = _niches_for_mode(icp, mode, req.manual_niches)
    if not niches:
        niches = [req.source_input or
                  ("parceiros estratégicos" if mode == "partners" else "empresas")]

    drafts: list[LeadDraft] = []
    seen: set[tuple] = set()
    seen_domains: set[str] = set()  # P4
    n = max(1, len(niches))
    base_label = "PARCEIROS" if mode == "partners" else "VENDA DIRETA"
    label = f"{base_label} · {label_suffix}" if label_suffix else base_label
    progress(f"[{label}] {n} nicho(s) a explorar: {', '.join(niches[:5])}"
             + ("…" if len(niches) > 5 else ""),
             pct_offset)

    def _domain(u: str) -> str:
        try:
            h = (urlparse(u if "://" in u else "https://" + u).hostname or "").lower()
            return h.removeprefix("www.")
        except Exception:
            return ""

    for idx, niche in enumerate(niches):
        query = _build_query(niche, req)
        progress(f"[{label}] ({idx+1}/{n}) Buscando 3 fontes em paralelo: {query}",
                 pct_offset + int(idx / n * (pct_budget * 0.45)))

        # P1 — Paraleliza Google Maps + Bing + DuckDuckGo
        places, bing_results, ddg_results = [], [], []
        # Helpers locais para instrumentação de scrapers
        def _run_scraper(source: str, fn, *args, **kwargs):
            import time as _t
            t0 = _t.perf_counter()
            ok = True
            err_msg = ""
            results = []
            blocked = False
            try:
                results = fn(*args, **kwargs) or []
            except Exception as ex:  # noqa: BLE001
                ok = False
                err_msg = str(ex)
                low = err_msg.lower()
                if any(k in low for k in ("captcha", "blocked", "429", "rate")):
                    blocked = True
                raise
            finally:
                try:
                    from app.web.audit import log_scraper_run, current_user_id
                    log_scraper_run(
                        user_id=current_user_id(),
                        source=source, query=query,
                        city=req.city, state=req.state,
                        results=len(results) if isinstance(results, list) else 0,
                        duration_ms=int((_t.perf_counter() - t0) * 1000),
                        success=ok, error=err_msg, blocked=blocked,
                    )
                except Exception:
                    pass
            return results

        with ThreadPoolExecutor(max_workers=3) as ex:
            f_gmaps = ex.submit(_run_scraper, "google_maps", search_google_maps, query, max_results=req.max_per_niche)
            f_bing = ex.submit(_run_scraper, "bing", search_bing, query, max_results=max(5, req.max_per_niche // 2))
            f_ddg = ex.submit(_run_scraper, "duckduckgo", search_duckduckgo, query, max_results=max(5, req.max_per_niche // 2))
            try:
                places = f_gmaps.result() or []
            except Exception as e:
                err = str(e)
                places = []
                if "Executable doesn't exist" in err or "playwright install" in err.lower():
                    progress("⚠ Playwright não instalado — Google Maps desativado. "
                             "Rode: .venv/bin/python -m playwright install chromium",
                             pct_offset + int(idx / n * (pct_budget * 0.45)))
                else:
                    log.error(f"Google Maps falhou '{query}': {e}")
            try:
                bing_results = _filter_bing_results(f_bing.result() or [])
            except Exception as e:
                log.warning(f"Bing falhou '{query}': {e}")
                bing_results = []
            try:
                ddg_results = _filter_bing_results(f_ddg.result() or [])
            except Exception as e:
                log.warning(f"DDG falhou '{query}': {e}")
                ddg_results = []

        progress(f"[{label}] {query}: GMaps={len(places)} Bing={len(bing_results)} DDG={len(ddg_results)}",
                 pct_offset + int(idx / n * (pct_budget * 0.45)) + 2)

        # ingest google maps
        for p in places:
            key = (p.name.lower().strip(), p.city.lower().strip(), p.phone)
            if key in seen:
                continue
            seen.add(key)
            d_url = _domain(p.website or "")
            if d_url:
                seen_domains.add(d_url)
            drafts.append(LeadDraft(
                name=p.name, niche=p.niche or niche,
                city=p.city or req.city, state=p.state or req.state,
                country=req.country, address=p.address, website=p.website,
                phone=p.phone, google_rating=p.rating, google_reviews=p.reviews,
                prospection_mode=mode, tags=_default_tag_for_mode(mode),
            ))

        # ingest bing + ddg (P4: evita duplicar dom)
        for r in bing_results + ddg_results:
            host = r.get("url", "")
            d_url = _domain(host)
            if not host or d_url in seen_domains:
                continue
            key = (r.get("title", "").lower().strip(), "", "")
            if key in seen:
                continue
            seen.add(key); seen_domains.add(d_url)
            drafts.append(LeadDraft(
                name=r.get("title", "")[:200], niche=niche,
                city=req.city, state=req.state, country=req.country,
                website=host,
                prospection_mode=mode, tags=_default_tag_for_mode(mode),
            ))

    # P6 — limita por nicho ANTES de enriquecer (custoso)
    by_niche: dict[str, list[LeadDraft]] = {}
    for d in drafts:
        by_niche.setdefault(d.niche or "_", []).append(d)
    capped: list[LeadDraft] = []
    dropped_cap = 0
    for niche_key, items in by_niche.items():
        if len(items) > _MAX_ENRICH_PER_NICHE:
            dropped_cap += len(items) - _MAX_ENRICH_PER_NICHE
            capped.extend(items[:_MAX_ENRICH_PER_NICHE])
        else:
            capped.extend(items)
    if dropped_cap:
        progress(f"[{label}] cap por nicho: {dropped_cap} leads excedentes ignorados (mantém top {_MAX_ENRICH_PER_NICHE}/nicho)",
                 pct_offset + int(pct_budget * 0.48))
    drafts = capped
    total = max(1, len(drafts))

    # P2 — Paraleliza enriquecimento de site
    progress(f"[{label}] Enriquecendo {total} empresas em paralelo (×{_ENRICH_WORKERS})…",
             pct_offset + int(pct_budget * 0.5))
    targets = [d for d in drafts if d.website]
    if targets:
        done = [0]
        with ThreadPoolExecutor(max_workers=_ENRICH_WORKERS) as ex:
            futures = {ex.submit(enrich_from_website, d): d for d in targets}
            for fut in as_completed(futures):
                done[0] += 1
                if done[0] % 5 == 0 or done[0] == len(targets):
                    progress(f"[{label}] Enriquecidas {done[0]}/{len(targets)}",
                             pct_offset + int(pct_budget * 0.5)
                             + int(done[0] / len(targets) * (pct_budget * 0.25)))
                try:
                    fut.result()
                except Exception as e:  # noqa: BLE001
                    d = futures[fut]
                    log.debug(f"Enrich falhou {d.website}: {e}")

    if req.use_ai_qualification and business_summary:
        progress(f"[{label}] IA qualificando {total} leads…",
                 pct_offset + int(pct_budget * 0.75))
        for i, d in enumerate(drafts):
            progress(f"[{label}] ({i+1}/{total}) IA qualificando {d.name}",
                     pct_offset + int(pct_budget * 0.75) + int(i / total * (pct_budget * 0.24)))
            payload = d.model_dump()
            # injeta site_excerpt para a IA
            if d.extra and isinstance(d.extra, dict):
                payload["site_excerpt"] = d.extra.get("site_excerpt", "")
            try:
                q = qualify_lead(business_summary, payload, mode=mode)
                d.score = int(q.get("score") or 0)
                d.score_reason = (q.get("reason") or "").strip()
                d.pitch = (q.get("pitch") or "").strip()
                d.match_score = int(q.get("match_score") or 0)
                d.why_matters = (q.get("why_matters") or "").strip()
                d.opportunity_when = (q.get("opportunity_when") or "").strip()[:120]
                d.opportunity_channel = (q.get("opportunity_channel") or "").strip()[:40]
                d.opportunity_offer = (q.get("opportunity_offer") or "").strip()
                d.ticket_estimate = (q.get("ticket_estimate") or "").strip()[:60]
                d.revenue_year_estimate = (q.get("revenue_year_estimate") or "").strip()[:60]
                d.follow_up_text = (q.get("follow_up_text") or "").strip()
                ai_tags = q.get("tags") or []
                if isinstance(ai_tags, list):
                    base_tag = _default_tag_for_mode(mode)
                    merged = [base_tag] + [str(t).strip() for t in ai_tags if str(t).strip()]
                    d.tags = ", ".join(dict.fromkeys(merged))[:500]
            except AIClientError as e:
                log.warning(f"IA indisponível: {e}")
                break
            except Exception as e:  # noqa: BLE001
                log.debug(f"Qualificação falhou: {e}")
            # prioridade baseada em score + match + sinais
            d.priority = compute_priority(d.score, d.match_score, d.buying_signals or [])
    else:
        # sem IA: prioridade baseada apenas em sinais detectados
        for d in drafts:
            d.priority = compute_priority(d.score, d.match_score, d.buying_signals or [])
    return drafts


def _normalize_products(raw: list) -> list[dict]:
    """Sanitiza a lista de produtos vinda da IA."""
    out: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue

        def _list(k: str) -> list[str]:
            v = item.get(k) or []
            return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []

        out.append({
            "name": name[:80],
            "description": (item.get("description") or "").strip()[:240],
            "recommended_mode": (item.get("recommended_mode") or "").strip(),
            "direct_clients": _list("direct_clients"),
            "direct_keywords": _list("direct_keywords"),
            "partner_segments": _list("partner_segments"),
            "partner_keywords": _list("partner_keywords"),
        })
    return out[:6]


def _analyze_input(req: HuntRequest, progress: ProgressFn) -> tuple[ICPProfile, str]:
    # Reusa análise prévia se já foi feita no fluxo "Analisar Site".
    if req.preloaded_icp:
        try:
            icp = ICPProfile.model_validate(req.preloaded_icp)
            return icp, req.preloaded_summary or icp.summary or icp.business_type or req.source_input
        except Exception as e:  # noqa: BLE001
            log.debug(f"preloaded_icp inválido, re-analisando: {e}")

    icp = ICPProfile()
    business_summary = req.source_input
    if not req.source_input:
        return icp, business_summary

    # Cache de análise (TTL 7d)
    cached = AnalysisCacheRepository.get(req.source_input, req.is_website)
    if cached and cached.get("icp"):
        try:
            progress(f"♻ Cache: usando análise de {cached['created_at'].strftime('%d/%m %H:%M')} "
                     f"({cached['hits']}ª reuso)", 14)
            icp = ICPProfile.model_validate(cached["icp"])
            return icp, cached.get("summary") or icp.summary or icp.business_type or req.source_input
        except Exception as e:  # noqa: BLE001
            log.debug(f"cache inválido, re-analisando: {e}")

    if req.is_website:
        progress("Analisando site informado…", 6)
        site = scrape_site(req.source_input)
        # Inclui headings (é onde geralmente estão os nomes de produtos/serviços)
        headings_txt = " | ".join(site.headings or [])
        text = " ".join(filter(None, [site.title, site.description,
                                       headings_txt, site.text]))
    else:
        text = req.source_input

    try:
        progress("Consultando IA para identificar ICP e estratégia…", 14)
        data = analyze_site(req.source_input, text)
        icp = ICPProfile.model_validate({
            "business_type": data.get("business_type", ""),
            "summary": data.get("summary", ""),
            "ideal_clients": data.get("ideal_clients") or [],
            "keywords": data.get("keywords") or [],
            "pain_points": data.get("pain_points") or [],
            "commercial_score": int(data.get("commercial_score") or 0),
            "recommended_mode": (data.get("recommended_mode") or "").strip(),
            "recommended_reason": (data.get("recommended_reason") or "").strip(),
            "direct_clients": data.get("direct_clients") or [],
            "direct_keywords": data.get("direct_keywords") or [],
            "partner_segments": data.get("partner_segments") or [],
            "partner_keywords": data.get("partner_keywords") or [],
            "products": _normalize_products(data.get("products") or []),
        })
        business_summary = icp.summary or icp.business_type or req.source_input
        # Salva no cache
        try:
            AnalysisCacheRepository.put(
                req.source_input, req.is_website,
                icp.model_dump(), business_summary,
            )
        except Exception as e:  # noqa: BLE001
            log.debug(f"falha ao salvar cache: {e}")
    except AIClientError as e:
        log.warning(f"IA indisponível: {e}")

    return icp, business_summary


@dataclass
class AnalysisResult:
    icp: ICPProfile
    business_summary: str


def analyze_business(source_input: str, is_website: bool,
                     progress: ProgressFn = _noop,
                     force_refresh: bool = False) -> AnalysisResult:
    """Apenas analisa o site/descrição e retorna o ICP + produtos detectados.

    Usado pelo fluxo "Analisar Site" (passo 1) ANTES da prospecção real,
    para o usuário escolher quais produtos atacar.
    """
    progress("Iniciando análise…", 2)
    if force_refresh:
        AnalysisCacheRepository.invalidate(source_input, is_website)
    req = HuntRequest(source_input=source_input, is_website=is_website)
    icp, summary = _analyze_input(req, progress)
    progress("✔ Análise concluída", 100)
    return AnalysisResult(icp=icp, business_summary=summary)


def generate_product_details(product_name: str,
                              business_summary: str = "") -> dict:
    """Wrapper UI-friendly: retorna dict normalizado pronto para card."""
    if not product_name.strip():
        return {}
    try:
        raw = generate_product(product_name.strip(), business_summary)
    except AIClientError as e:
        log.warning(f"generate_product falhou: {e}")
        return {
            "name": product_name.strip(),
            "description": "",
            "recommended_mode": "direct_sale",
            "direct_keywords": [product_name.strip()],
            "direct_clients": [],
            "partner_keywords": [],
            "partner_segments": [],
        }
    normalized = _normalize_products([raw])
    return normalized[0] if normalized else {}


def hunt_leads(req: HuntRequest, progress: ProgressFn = _noop) -> HuntResult:
    progress("Iniciando…", 1)
    icp, business_summary = _analyze_input(req, progress)

    chosen = req.mode if req.mode in ("direct_sale", "partners", "both") else "direct_sale"
    search_id = SearchRepository.create(
        source_input=req.source_input,
        niche=", ".join(req.manual_niches),
        city=req.city, state=req.state, country=req.country,
        business_summary=business_summary,
        icp_json=icp.model_dump(),
        prospection_mode=chosen,
        recommended_mode=icp.recommended_mode,
    )

    drafts: list[LeadDraft] = []
    base_pct = 22

    # Plano de execução: lista de (label, mode, niches_override|None)
    plan: list[tuple[str, str, list[str] | None]] = []
    if req.selected_products:
        for product in req.selected_products:
            p_mode = (product.get("mode") or "direct_sale").strip()
            if p_mode not in ("direct_sale", "partners", "both"):
                p_mode = "direct_sale"
            modes_for_p = ["direct_sale", "partners"] if p_mode == "both" else [p_mode]
            for m in modes_for_p:
                niches = _niches_from_product(product, m)
                if not niches:
                    # fallback: usa keywords globais do ICP para o modo
                    niches = _niches_for_mode(icp, m, req.manual_niches)
                plan.append((product.get("name", ""), m, niches))
    else:
        modes = ["direct_sale", "partners"] if chosen == "both" else [chosen]
        for m in modes:
            plan.append(("", m, None))

    pct_per_step = max(1, int(75 / max(1, len(plan))))

    for i, (label_suffix, m, niches_override) in enumerate(plan):
        step_label = f"{m}" + (f" / {label_suffix}" if label_suffix else "")
        progress(f"Etapa {i+1}/{len(plan)}: {step_label}…", base_pct + i * pct_per_step)
        drafts += _run_for_mode(
            req=req, icp=icp, business_summary=business_summary, mode=m,
            progress=progress,
            pct_offset=base_pct + i * pct_per_step,
            pct_budget=pct_per_step,
            niches_override=niches_override,
            label_suffix=label_suffix,
        )

    progress(f"💬 Renderizando mensagens de {len(drafts)} leads…", 95)
    rows: list[dict] = []
    discarded_contact = 0
    discarded_local = 0
    drop_log: list[tuple[str, str]] = []
    for d in drafts:
        row = d.to_db()
        row["search_id"] = search_id
        # B3 — minimal contact (mantido como sanidade)
        if not has_minimum_contact(row):
            discarded_contact += 1
            continue
        # B6+B7+B8+B9 — filtros locais rápidos
        ok, reason = passes_local_filters(row)
        if not ok:
            discarded_local += 1
            drop_log.append((row.get("name", "?"), reason))
            continue
        # injeta site_excerpt para uso posterior
        if d.extra and isinstance(d.extra, dict):
            row["site_excerpt"] = d.extra.get("site_excerpt", "")
        rows.append(row)

    progress(f"⚠ filtros locais: -{discarded_contact} sem contato, "
             f"-{discarded_local} reprovados (B6/B7/B8/B9). Sobraram {len(rows)}.", 96)
    for nm, rsn in drop_log[:10]:
        log.info(f"DROP local: {nm} — {rsn}")

    # B10 — IA classifica em lotes (10/call). Falha = mantém todos.
    if rows:
        progress(f"🧠 IA validando {len(rows)} leads em lotes de 10…", 97)
        kept, dropped_ai = filter_with_ai(
            rows, business_summary=business_summary, batch_size=10,
        )
        if dropped_ai:
            progress(f"🧠 IA descartou {len(dropped_ai)} leads de baixa qualidade.", 97)
            for nm, rsn in dropped_ai[:10]:
                log.info(f"DROP IA: {nm} — {rsn}")
        rows = kept

    # Renderiza mensagens (sem IA — opener é sob demanda no botão)
    for i, row in enumerate(rows, 1):
        if i % 20 == 0 or i == len(rows):
            progress(f"💬 Mensagens {i}/{len(rows)}…", 98)
        try:
            msgs = build_messages_for_lead(row, use_ai=False)
            row.update(msgs)
        except Exception as e:  # noqa: BLE001
            log.debug(f"build_messages falhou: {e}")
        # remove campo auxiliar antes de upsert
        row.pop("site_excerpt", None)

    progress(f"💾 Salvando {len(rows)} leads no banco…", 99)
    inserted = LeadRepository.upsert_many(rows)
    SearchRepository.update_total(search_id, inserted)
    progress(f"✔ {inserted} novos leads salvos. Concluído.", 100)

    direct_count = sum(1 for d in drafts if d.prospection_mode == "direct_sale")
    partners_count = sum(1 for d in drafts if d.prospection_mode == "partners")
    return HuntResult(
        search_id=search_id, icp=icp, leads=drafts,
        direct_count=direct_count, partners_count=partners_count,
    )
