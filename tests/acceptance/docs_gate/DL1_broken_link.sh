#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

ensure_clean_tree

TMP_DOC="docs/projects/core-pillars/__tmp_DL1.md"
cleanup() { rm -f "$TMP_DOC"; }
trap cleanup EXIT

cat > "$TMP_DOC" <<'EOF'
# Temp
Date: 2026-02-24
Status: active
## Objective
link test
[broken](./__missing_target__.md)
EOF

assert_fail_contains "E_DOCS_LINK_MISSING" $DOCS_LINT_CMD --json
echo "DL1_OK"

