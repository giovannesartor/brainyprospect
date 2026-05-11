"""Ponto de entrada do Brainy Prospect."""
from __future__ import annotations

import sys
from pathlib import Path

# Permite executar `python main.py` sem instalar como pacote
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import run


if __name__ == "__main__":
    sys.exit(run())
