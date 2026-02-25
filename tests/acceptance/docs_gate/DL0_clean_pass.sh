#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

ensure_clean_tree
$DOCS_LINT_CMD --json >/dev/null
echo "DL0_OK"

