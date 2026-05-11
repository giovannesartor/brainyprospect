"""Endpoints extras: today, lookalike, objections, charts, push, monitoring."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import LeadRepository, SearchRepository
from app.services.ai.client import _chat, AIClientError
from app.services.lead_hunter import HuntRequest, hunt_leads
from app.web.deps import require_user
from app.web.jobs import JOBS

router = APIRouter(prefix="/api", tags=["extras"])


# =============================================================
# TODAY — Top leads quentes + pendências do dia
# =============================================================
@router.get("/today")
def today(_: dict = Depends(require_user)):
    hot = LeadRepository.query(
        priority="maxima", status="novo", limit=10
    )
    if len(hot) < 10:
        more = LeadRepository.query(priority="alta", status="novo", limit=10 - len(hot))
        seen = {l["id"] for l in hot}
        hot += [l for l in more if l["id"] not in seen]

    contacted = LeadRepository.query(status="contatado", limit=10)
    awaiting = LeadRepository.query(status="respondeu", limit=10)
    closing = LeadRepository.query(status="proposta", limit=10)

    stats = LeadRepository.stats()
    pipeline = LeadRepository.pipeline_stats()

    return {
        "hot_leads": hot,
        "in_contact": contacted,
        "responded": awaiting,
        "closing": closing,
        "summary": {
            "total_hot": pipeline.get("novo", 0),
            "in_pipeline": sum(pipeline.get(k, 0) for k in ("contatado", "respondeu", "reuniao", "proposta")),
            "won": pipeline.get("fechado", 0),
            "total_leads": stats.get("total", 0),
        },
    }


# =============================================================
# CHARTS — séries para o dashboard
# =============================================================
@router.get("/charts")
def charts(_: dict = Depends(require_user)):
    per_day = LeadRepository.leads_per_day(14)
    pipeline = LeadRepository.pipeline_stats()
    priority = LeadRepository.priority_distribution()
    cities = LeadRepository.top_cities(8)

    # Conversão por nicho (todos -> contatado/fechado)
    all_leads = LeadRepository.query(limit=5000)
    by_niche: dict[str, dict[str, int]] = {}
    for l in all_leads:
        n = (l.get("niche") or "outros").strip() or "outros"
        b = by_niche.setdefault(n, {"total": 0, "contacted": 0, "won": 0})
        b["total"] += 1
        if l.get("status") in ("contatado", "respondeu", "reuniao", "proposta", "fechado"):
            b["contacted"] += 1
        if l.get("status") == "fechado":
            b["won"] += 1
    # Top 8 por total
    top_niches = sorted(by_niche.items(), key=lambda kv: kv[1]["total"], reverse=True)[:8]
    niche_conv = [
        {
            "niche": k,
            "total": v["total"],
            "contacted": v["contacted"],
            "won": v["won"],
            "rate": round((v["won"] / v["total"]) * 100, 1) if v["total"] else 0.0,
        }
        for k, v in top_niches
    ]

    return {
        "per_day": [{"date": d, "count": n} for d, n in per_day],
        "pipeline": pipeline,
        "priority": priority,
        "cities": [{"city": c, "count": n} for c, n in cities],
        "niche_conversion": niche_conv,
    }


# =============================================================
# LOOKALIKE — usar 1 lead/cliente como referência para nova hunt
# =============================================================
class LookalikeIn(BaseModel):
    lead_id: Optional[int] = None
    source_input: Optional[str] = None
    is_website: bool = True
    max_per_niche: int = Field(default=15, ge=1, le=40)
    city: Optional[str] = None
    state: Optional[str] = None
    mode: str = "direct_sale"


@router.post("/hunt-lookalike")
def hunt_lookalike(payload: LookalikeIn, user: dict = Depends(require_user)):
    """Recebe um lead existente OU um site/descrição e dispara uma hunt
    procurando empresas similares (mesmo perfil/nicho/região)."""
    source = payload.source_input
    is_site = payload.is_website
    city = payload.city
    state = payload.state
    seed_name = ""

    if payload.lead_id:
        lead = LeadRepository.get(payload.lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead de referência não encontrado.")
        seed_name = lead.get("name") or ""
        # Prefere site; cai para nome+nicho como descrição
        site = (lead.get("website") or "").strip()
        if site:
            source = site
            is_site = True
        else:
            niche = lead.get("niche") or ""
            source = f"Empresa similar a {seed_name}, do nicho {niche}".strip()
            is_site = False
        city = city or lead.get("city")
        state = state or lead.get("state")

    if not source:
        raise HTTPException(status_code=400, detail="Forneça lead_id ou source_input.")

    req = HuntRequest(
        source_input=source,
        is_website=is_site,
        city=(city or ""),
        state=(state or ""),
        max_per_niche=payload.max_per_niche,
        use_ai_qualification=True,
        mode=payload.mode,
    )

    def task(progress):
        progress(f"🔍 Lookalike de {seed_name or source}", 5)
        result = hunt_leads(req, progress=progress)
        return {
            "search_id": result.search_id,
            "total_leads": len(result.leads),
            "seed": seed_name or source,
        }

    job_id = JOBS.submit("lookalike", task, user_id=user["id"])
    return {"job_id": job_id, "seed": seed_name or source}


# =============================================================
# OBJECTIONS — IA responde objeções comuns
# =============================================================
class ObjectionIn(BaseModel):
    objection: str
    context: Optional[str] = None
    lead_id: Optional[int] = None


@router.post("/objections")
def objections(payload: ObjectionIn, _: dict = Depends(require_user)):
    if not payload.objection.strip():
        raise HTTPException(status_code=400, detail="Informe a objeção.")

    extra = ""
    if payload.lead_id:
        lead = LeadRepository.get(payload.lead_id)
        if lead:
            extra = (
                f"\n\nContexto do lead:\n"
                f"- Nome: {lead.get('name')}\n"
                f"- Nicho: {lead.get('niche')}\n"
                f"- Cidade: {lead.get('city')}\n"
                f"- Resumo: {lead.get('why_matters') or ''}\n"
            )
    if payload.context:
        extra += f"\nContexto extra: {payload.context}\n"

    prompt = f"""Você é um SDR sênior. Recebi a seguinte objeção de um prospect:

"{payload.objection.strip()}"
{extra}

Gere uma resposta JSON com 3 abordagens de resposta diferentes (curta, consultiva, com prova social),
cada uma com no máximo 4 linhas, em PT-BR, tom humano e direto.
Formato:
{{
  "responses": [
    {{"strategy": "curta", "text": "..."}},
    {{"strategy": "consultiva", "text": "..."}},
    {{"strategy": "prova_social", "text": "..."}}
  ],
  "tip": "uma dica curta sobre como conduzir após a resposta"
}}"""
    try:
        out = _chat(prompt, json_mode=True)
    except AIClientError as e:
        raise HTTPException(status_code=503, detail=f"IA indisponível: {e}")
    if not out.get("responses"):
        raise HTTPException(status_code=502, detail="A IA não retornou respostas válidas.")
    return out


# =============================================================
# BRAINY CHAT — perguntas sobre os leads / estratégia
# =============================================================
class ChatIn(BaseModel):
    message: str
    history: list[dict[str, str]] = []


@router.post("/brainy-chat")
def brainy_chat(payload: ChatIn, _: dict = Depends(require_user)):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Mensagem vazia.")
    stats = LeadRepository.stats()
    pipeline = LeadRepository.pipeline_stats()
    ctx = (
        f"Você é a Brainy, IA de vendas B2B do usuário. "
        f"Hoje ele tem {stats.get('total', 0)} leads, "
        f"{pipeline.get('novo', 0)} novos, {pipeline.get('contatado', 0)} contatados, "
        f"{pipeline.get('fechado', 0)} fechados. "
        f"Responda de forma curta (até 6 linhas), prática, em PT-BR. Não invente dados."
    )
    hist = ""
    for m in payload.history[-6:]:
        role = m.get("role") or "user"
        hist += f"\n[{role}] {m.get('content','')}"
    prompt = f"{ctx}{hist}\n[user] {payload.message.strip()}\n\nResponda em JSON: {{\"reply\": \"...\"}}"
    try:
        out = _chat(prompt, json_mode=True)
    except AIClientError as e:
        raise HTTPException(status_code=503, detail=f"IA indisponível: {e}")
    reply = out.get("reply") if isinstance(out, dict) else None
    if not reply and isinstance(out, dict):
        # fallback: às vezes a IA devolve outro formato
        reply = out.get("text") or out.get("answer") or ""
    return {"reply": reply or "Sem resposta."}


# =============================================================
# WEB PUSH — versão simplificada (in-memory, opcional)
# Implementação mínima: registra subscription e expõe lista para debug.
# (Push real requer VAPID + chave; usamos Notification API local para MVP.)
# =============================================================
_PUSH_SUBS: dict[int, list[dict[str, Any]]] = {}


@router.post("/push/subscribe")
def push_subscribe(sub: dict[str, Any], user: dict = Depends(require_user)):
    arr = _PUSH_SUBS.setdefault(user["id"], [])
    if sub not in arr:
        arr.append(sub)
    return {"ok": True, "count": len(arr)}


@router.delete("/push/subscribe")
def push_unsubscribe(user: dict = Depends(require_user)):
    _PUSH_SUBS.pop(user["id"], None)
    return {"ok": True}
