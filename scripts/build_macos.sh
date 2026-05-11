#!/usr/bin/env bash
# Build do .app via PyInstaller
set -euo pipefail
source .venv/bin/activate
rm -rf build dist
pyinstaller LeadHunterAI.spec --noconfirm
echo "✔ Gerado: dist/LeadHunterAI.app"
