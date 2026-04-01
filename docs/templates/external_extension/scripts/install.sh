#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${ORKET_SDK_INSTALL_SPEC:-}" ]]; then
  echo "Set ORKET_SDK_INSTALL_SPEC to a pip install spec for orket-extension-sdk." >&2
  exit 2
fi

python -m pip install --upgrade pip
python -m pip install "${ORKET_SDK_INSTALL_SPEC}"

if ! command -v orket >/dev/null 2>&1; then
  if [[ -z "${ORKET_HOST_INSTALL_SPEC:-}" ]]; then
    echo "The orket CLI is required. Install it first or set ORKET_HOST_INSTALL_SPEC." >&2
    exit 2
  fi
  python -m pip install "${ORKET_HOST_INSTALL_SPEC}"
fi

python -m pip install -e ".[dev]"

echo "Install complete."
