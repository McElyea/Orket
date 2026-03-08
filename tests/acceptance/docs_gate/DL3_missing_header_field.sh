#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

ensure_clean_tree
setup_docs_fixture

TMP_DOC="$DOCS_GATE_ROOT/__tmp_DL3.md"
cleanup() {
  rm -f "$TMP_DOC"
  cleanup_docs_fixture
}
trap cleanup EXIT

cat > "$TMP_DOC" <<'EOF'
# Temp
Date: 2026-02-24
Status: active
## NotObjective
EOF

assert_fail_contains "E_DOCS_HEADER_MISSING" $DOCS_LINT_CMD --json
echo "DL3_OK"
