"""Aplicação FastAPI — Brainy Prospect Web."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database.db import init_db
from app.utils.logger import get_logger
from app.web.audit import AuditMiddleware
from app.web.deps import get_current_user_optional
from app.web.routes import admin as admin_routes
from app.web.routes import auth as auth_routes
from app.web.routes import extras as extras_routes
from app.web.routes import leads as leads_routes
from app.web.routes import telemetry as telemetry_routes
from app.web.users import UserRepository

log = get_logger("web")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _seed_admin() -> None:
    email = os.environ.get("ADMIN_EMAIL", "giovannesartor@gmail.com").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "Giotop12@")
    name = os.environ.get("ADMIN_NAME", "Giovanne Sartor")
    try:
        u = UserRepository.ensure_admin(email=email, password=password, full_name=name)
        log.info(f"Admin garantido: {u['email']}")
    except Exception as e:  # noqa: BLE001
        log.error(f"Falha ao garantir admin: {e}")


def _safe_user(user: dict | None) -> dict:
    """Serializa datas como ISO para uso em templates/JSON."""
    if not user:
        return {}
    out = {}
    for k, v in user.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def create_app() -> FastAPI:
    app = FastAPI(
        title="Brainy Prospect",
        description="Plataforma B2B de prospecção com IA — versão web.",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    # CORS — permissivo (mesmo origin via cookie). Ajuste em produção.
    allowed = os.environ.get("CORS_ORIGINS", "*")
    origins = [o.strip() for o in allowed.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Audit log middleware (registra cada chamada relevante a /api/*)
    app.add_middleware(AuditMiddleware)

    @app.on_event("startup")
    def _startup():
        init_db()
        _seed_admin()
        log.info("Brainy Prospect Web pronto.")

    # API routers
    app.include_router(auth_routes.router)
    app.include_router(leads_routes.router)
    app.include_router(extras_routes.router)
    app.include_router(telemetry_routes.router)
    app.include_router(admin_routes.router)

    # Static + templates
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "brainy-prospect"}

    # PWA — manifest e service worker servidos no root
    from fastapi.responses import FileResponse, Response

    @app.get("/manifest.webmanifest")
    def manifest():
        f = STATIC_DIR / "manifest.webmanifest"
        if f.exists():
            return FileResponse(str(f), media_type="application/manifest+json")
        return Response(status_code=404)

    @app.get("/sw.js")
    def service_worker():
        f = STATIC_DIR / "sw.js"
        if f.exists():
            return FileResponse(str(f), media_type="application/javascript",
                                headers={"Service-Worker-Allowed": "/"})
        return Response(status_code=404)

    # ---- Páginas (server-rendered) ----
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        user = get_current_user_optional(request)
        if user:
            return RedirectResponse("/app")
        return templates.TemplateResponse(request, "landing.html", {"user": None})

    @app.get("/login", response_class=HTMLResponse)
    def page_login(request: Request):
        return templates.TemplateResponse(request, "login.html", {"user": None})

    @app.get("/register", response_class=HTMLResponse)
    def page_register(request: Request):
        return templates.TemplateResponse(request, "register.html", {"user": None})

    @app.get("/app", response_class=HTMLResponse)
    def page_app(request: Request):
        user = get_current_user_optional(request)
        if not user:
            return RedirectResponse("/login")
        return templates.TemplateResponse(request, "app.html", {"user": _safe_user(user)})

    @app.get("/admin", response_class=HTMLResponse)
    def page_admin(request: Request):
        user = get_current_user_optional(request)
        if not user:
            return RedirectResponse("/login")
        if user.get("role") != "admin":
            return RedirectResponse("/app")
        return templates.TemplateResponse(request, "admin.html", {"user": _safe_user(user)})

    return app


app = create_app()
