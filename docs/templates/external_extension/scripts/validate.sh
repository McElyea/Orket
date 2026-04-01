#!/usr/bin/env bash
set -euo pipefail

if ! command -v orket >/dev/null 2>&1; then
  echo "The orket CLI is required for host validation." >&2
  exit 2
fi

python -m orket_extension_sdk.validate . --strict --json
python -m orket_extension_sdk.import_scan src --json
orket ext validate . --strict --json
python -m pytest -q tests/

echo "Validation complete."
