#!/usr/bin/env bash
set -euo pipefail

python -m orket_extension_sdk.validate . --json
python -m orket_extension_sdk.import_scan src --json
if command -v orket >/dev/null 2>&1; then
  orket ext validate . --json
elif python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('orket') else 1)" >/dev/null 2>&1; then
  python -m orket.interfaces.orket_bundle_cli ext validate . --json
else
  echo "Skipping host CLI extension validation (orket CLI/package unavailable)."
fi
PYTHONPATH=src python -m pytest -q tests/

echo "Validation complete."
