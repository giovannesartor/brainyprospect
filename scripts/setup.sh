#!/usr/bin/env bash
# Setup local de desenvolvimento (macOS)
set -euo pipefail

PYTHON=${PYTHON:-python3.12}
echo "▶ Criando virtualenv com $PYTHON…"
$PYTHON -m venv .venv
source .venv/bin/activate

echo "▶ Atualizando pip…"
pip install --upgrade pip wheel

echo "▶ Instalando dependências…"
pip install -r requirements.txt

echo "▶ Instalando navegador do Playwright (Chromium)…"
python -m playwright install chromium

echo "✔ Pronto. Para rodar:"
echo "   source .venv/bin/activate && python main.py"
