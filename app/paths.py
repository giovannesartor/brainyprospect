"""Caminhos centrais do projeto.

Resolve diretórios tanto em modo desenvolvimento quanto quando empacotado
via PyInstaller (``.app``).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _project_root() -> Path:
    """Retorna a raiz do projeto (ou recurso embarcado)."""
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def _user_data_dir() -> Path:
    """Diretório de dados de usuário (gravável mesmo em .app empacotado).

    Em ambientes web/cloud (Railway, Docker), defina BRAINY_DATA_DIR para
    apontar para um volume persistente (ex.: /data).
    """
    env_dir = os.environ.get("BRAINY_DATA_DIR")
    if env_dir:
        base = Path(env_dir)
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "BrainyProspect"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / "BrainyProspect"
    else:
        # Linux / containers — usa /data se existir, senão ~/.brainyprospect
        if Path("/data").exists() and os.access("/data", os.W_OK):
            base = Path("/data") / "brainyprospect"
        else:
            base = Path.home() / ".brainyprospect"
    base.mkdir(parents=True, exist_ok=True)
    return base


ROOT_DIR: Path = _project_root()
USER_DIR: Path = _user_data_dir()

CONFIG_DIR: Path = USER_DIR / "config"
LOGS_DIR: Path = USER_DIR / "logs"
EXPORTS_DIR: Path = USER_DIR / "exports"
DB_PATH: Path = USER_DIR / "brainyprospect.db"

DEFAULT_SETTINGS_FILE: Path = ROOT_DIR / "config" / "settings.default.json"
SETTINGS_FILE: Path = CONFIG_DIR / "settings.json"

ASSETS_DIR: Path = ROOT_DIR / "app" / "assets"
LOGO_PATH: Path = ROOT_DIR / "brainyprospect_logo.png"

for _d in (CONFIG_DIR, LOGS_DIR, EXPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
