#!/usr/bin/env bash
set -euo pipefail

ARGS=(scripts/check_release.py --dist-dir dist --json)
if [[ -n "${1:-}" ]]; then
  ARGS+=(--tag "$1")
fi

python "${ARGS[@]}"

echo "Release verification complete."
