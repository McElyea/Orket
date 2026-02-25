#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

ensure_clean_tree

CANON="docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md"
TMP="${CANON}.bak_dl2"

[[ -f "$CANON" ]] || die "canonical file not found: $CANON"
mv "$CANON" "$TMP"
cleanup() { mv "$TMP" "$CANON"; }
trap cleanup EXIT

assert_fail_contains "E_DOCS_CANONICAL_MISSING" $DOCS_LINT_CMD --json
echo "DL2_OK"

