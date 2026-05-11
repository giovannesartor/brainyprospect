"""Configuração centralizada de logging com loguru."""
from __future__ import annotations

import sys

from loguru import logger

from app.paths import LOGS_DIR

_configured = False


def setup_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{line}</cyan> - {message}",
    )
    logger.add(
        LOGS_DIR / "brainyprospect_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        level="DEBUG",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    _configured = True


def get_logger(name: str | None = None):
    if not _configured:
        setup_logging()
    return logger.bind(scope=name) if name else logger
