"""Rotas de leads, dashboard, hunts."""
from __future__ import annotations

import io
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.database import (
    CampaignRepository,
    LeadRepository,
    SearchRepository,
)
from app.services import exporter
from app.services.lead_hunter import HuntRequest, analyze_business, hunt_leads
from app.web.deps import require_user
from app.web.jobs import JOBS
from app.web.schemas import AnalyzeIn, CampaignIn, HuntIn, LeadUpdateIn

router = APIRouter(prefix="/api", tags=["app"])


# ---------- DASHBOARD ----------
@router.get("/dashboard")
def dashboard(_: dict = Depends(require_user)):
    stats = LeadRepository.stats()
    pipeline = LeadRepository.pipeline_stats()
    priority = LeadRepository.priority_distribution()
    per_day = LeadRepository.leads_per_day(14)
    cities = LeadRepository.top_cities(8)
    recent = SearchRepository.list_recent(10)
    return {
        "stats": stats,
        "pipeline": pipeline,
        "priority": priority,
        "per_day": per_day,
        "top_cities": cities,
        "recent_searches": recent,
    }


# ---------- LEADS ----------
@router.get("/leads")
def list_leads(
    text: str = "",
    city: Optional[str] = None,
    state: Optional[str] = None,
    niche: Optional[str] = None,
    min_score: int = 0,
    only_with_email: bool = False,
    only_with_whatsapp: bool = False,
    only_without_site: bool = False,
    prospection_mode: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    campaign_id: Optional[int] = None,
    limit: int = Query(default=200, le=2000),
    offset: int = 0,
    _: dict = Depends(require_user),
):
    rows = LeadRepository.query(
        text=text, city=city, state=state, niche=niche,
        min_score=min_score, only_with_email=only_with_email,
        only_with_whatsapp=only_with_whatsapp,
        only_without_site=only_without_site,
        prospection_mode=prospection_mode, priority=priority,
        status=status, campaign_id=campaign_id,
        limit=limit, offset=offset,
    )
    return {"items": rows, "count": len(rows)}


@router.get("/leads/{lead_id}")
def get_lead(lead_id: int, _: dict = Depends(require_user)):
    lead = LeadRepository.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    return lead


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, patch: LeadUpdateIn, _: dict = Depends(require_user)):
    changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    if not changes:
        return {"ok": True, "changed": 0}
    LeadRepository.update(lead_id, **changes)
    return {"ok": True, "changed": len(changes)}


@router.delete("/leads/{lead_id}")
def delete_lead(lead_id: int, _: dict = Depends(require_user)):
    LeadRepository.delete_many([lead_id])
    return {"ok": True}


@router.post("/leads/bulk-status")
def bulk_status(payload: dict[str, Any], _: dict = Depends(require_user)):
    ids = payload.get("ids") or []
    status = payload.get("status") or "novo"
    n = LeadRepository.bulk_update_status(list(map(int, ids)), status)
    return {"ok": True, "updated": n}


# ---------- EXPORT ----------
@router.get("/leads/export/{fmt}")
def export_leads(fmt: str, request: Request, user: dict = Depends(require_user)):
    rows = LeadRepository.query(limit=10000)
    fmt = fmt.lower()
    if fmt == "csv":
        path = exporter.export_csv(rows)
        media = "text/csv"
    elif fmt == "xlsx":
        path = exporter.export_xlsx(rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "json":
        path = exporter.export_json(rows)
        media = "application/json"
    else:
        raise HTTPException(status_code=400, detail="Formato inválido. Use csv|xlsx|json.")
    with open(path, "rb") as fh:
        data = fh.read()
    fname = str(path).split("/")[-1]
    # Audit
    try:
        import hashlib
        from app.web.audit import log_export
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
        log_export(
            user_id=user["id"], fmt=fmt, rows=len(rows),
            filters=dict(request.query_params),
            file_hash=hashlib.sha256(data).hexdigest()[:32],
            ip=ip,
        )
    except Exception:
        pass
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ---------- CAMPAIGNS ----------
@router.get("/campaigns")
def list_campaigns(_: dict = Depends(require_user)):
    return CampaignRepository.list_all()


@router.post("/campaigns")
def create_campaign(payload: CampaignIn, _: dict = Depends(require_user)):
    cid = CampaignRepository.create(
        name=payload.name, description=payload.description,
        target_mode=payload.target_mode, color=payload.color,
    )
    return {"id": cid}


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, _: dict = Depends(require_user)):
    CampaignRepository.delete(campaign_id)
    return {"ok": True}


# ---------- HUNTS / ANÁLISE ----------
@router.post("/analyze")
def analyze(payload: AnalyzeIn, _: dict = Depends(require_user)):
    """Análise síncrona (rápida — usa cache de IA)."""
    try:
        result = analyze_business(
            source_input=payload.source_input,
            is_website=payload.is_website,
            force_refresh=payload.force_refresh,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha na análise: {e}")
    icp = getattr(result, "icp", None)
    summary = getattr(result, "business_summary", "")
    icp_dict = icp.model_dump() if icp and hasattr(icp, "model_dump") else (icp or {})
    return {"icp": icp_dict, "business_summary": summary}


@router.post("/hunt")
def start_hunt(payload: HuntIn, user: dict = Depends(require_user)):
    """Inicia hunt em background. Retorna job_id para polling."""
    req = HuntRequest(
        source_input=payload.source_input,
        is_website=payload.is_website,
        manual_niches=payload.manual_niches,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        max_per_niche=payload.max_per_niche,
        use_ai_qualification=payload.use_ai_qualification,
        mode=payload.mode,
        selected_products=payload.selected_products,
        preloaded_icp=payload.preloaded_icp,
        preloaded_summary=payload.preloaded_summary,
    )

    def task(progress):
        # propaga user para scrapers/IA via context vars
        try:
            from app.web.audit import set_user_context
            from app.services.ai.client import set_ai_context
            set_user_context(user["id"])
            set_ai_context(user["id"], "hunt")
        except Exception:
            pass
        result = hunt_leads(req, progress=progress)
        return {
            "search_id": result.search_id,
            "total_leads": len(result.leads),
            "direct_count": result.direct_count,
            "partners_count": result.partners_count,
        }

    job_id = JOBS.submit("hunt", task, user_id=user["id"])
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, _: dict = Depends(require_user)):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return j


@router.get("/jobs")
def list_jobs(user: dict = Depends(require_user)):
    return JOBS.list_for(user_id=user["id"])


# ---------- SEARCHES ----------
@router.get("/searches")
def list_searches(limit: int = 50, _: dict = Depends(require_user)):
    return SearchRepository.list_recent(limit)
