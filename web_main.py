"""Entrypoint web para Railway/Heroku/Docker.

Uso local:
    uvicorn web_main:app --reload --port 8000

Em produção:
    uvicorn web_main:app --host 0.0.0.0 --port $PORT
"""
from app.web.main import app  # noqa: F401

__all__ = ["app"]
