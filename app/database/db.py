"""Configuração do SQLAlchemy.

Suporta SQLite (default local) e PostgreSQL (via DATABASE_URL — Railway/Heroku).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.paths import DB_PATH


class Base(DeclarativeBase):
    pass


def _build_engine():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Railway/Heroku às vezes entregam postgres:// — SQLAlchemy quer postgresql://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        # Garante driver psycopg2 implícito; ok deixar default
        return create_engine(url, echo=False, future=True, pool_pre_ping=True)
    return create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )


_engine = _build_engine()
IS_POSTGRES = _engine.url.get_backend_name().startswith("postgres")
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """Cria todas as tabelas (importa modelos para registrar metadata)."""
    from app.database import models  # noqa: F401  (registro de modelos)
    Base.metadata.create_all(_engine)
    _run_lightweight_migrations()


def _run_lightweight_migrations() -> None:
    """Adiciona colunas novas a bancos antigos (apenas SQLite)."""
    if IS_POSTGRES:
        # Em Postgres confiamos em create_all + (futuramente) Alembic.
        return
    needed = {
        "leads": [
            ("prospection_mode", "VARCHAR(20) DEFAULT 'direct_sale'"),
            ("tags", "VARCHAR(500) DEFAULT ''"),
            ("cnpj", "VARCHAR(20) DEFAULT ''"),
            ("company_size", "VARCHAR(40) DEFAULT ''"),
            ("employees_estimate", "INTEGER"),
            ("years_in_market", "INTEGER"),
            ("technologies", "VARCHAR(500) DEFAULT ''"),
            ("decision_makers", "JSON"),
            ("buying_signals", "JSON"),
            ("match_score", "INTEGER DEFAULT 0"),
            ("priority", "VARCHAR(20) DEFAULT 'media'"),
            ("why_matters", "TEXT DEFAULT ''"),
            ("opportunity_when", "VARCHAR(120) DEFAULT ''"),
            ("opportunity_channel", "VARCHAR(40) DEFAULT ''"),
            ("opportunity_offer", "TEXT DEFAULT ''"),
            ("ticket_estimate", "VARCHAR(60) DEFAULT ''"),
            ("revenue_year_estimate", "VARCHAR(60) DEFAULT ''"),
            ("observations", "TEXT DEFAULT ''"),
            ("follow_up_text", "TEXT DEFAULT ''"),
            ("last_contact_at", "DATETIME"),
            ("next_followup_at", "DATETIME"),
            ("campaign_id", "INTEGER"),
            ("message_a", "TEXT DEFAULT ''"),
            ("message_b", "TEXT DEFAULT ''"),
            ("message_opener", "VARCHAR(500) DEFAULT ''"),
            ("message_tone", "VARCHAR(20) DEFAULT ''"),
            ("send_status", "VARCHAR(30) DEFAULT 'nao_enviado'"),
            ("hot_score", "INTEGER DEFAULT 0"),
            ("followup_step", "INTEGER DEFAULT 0"),
        ],
        "searches": [
            ("prospection_mode", "VARCHAR(20) DEFAULT 'direct_sale'"),
            ("recommended_mode", "VARCHAR(20) DEFAULT ''"),
        ],
    }
    from sqlalchemy import text
    with _engine.begin() as conn:
        for table, columns in needed.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            for col, ddl in columns:
                if col not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"
                    )


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager transacional."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine():
    return _engine
