#!/usr/bin/env bash
set -euo pipefail

python scripts/validate_catalog.py
python scripts/detect_ecommerce.py
python scripts/prepare_assets.py

echo
echo "Preparación completada."
echo "Codex debe continuar con el matching, backup, carga, build y verificación definidos en AGENTS.md."
