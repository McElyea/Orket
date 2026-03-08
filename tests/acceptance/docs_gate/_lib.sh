#!/usr/bin/env bash
set -euo pipefail

DOCS_GATE_PROJECT="__tmp_docs_gate_fixture"
DOCS_GATE_ROOT="docs/projects/$DOCS_GATE_PROJECT"
DOCS_LINT_CMD=${DOCS_LINT_CMD:-"python scripts/governance/docs_lint.py --project $DOCS_GATE_PROJECT"}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

ensure_clean_tree() {
  if ! git diff --quiet || ! git diff --cached --quiet; then
    die "git working tree must be clean before running acceptance tests"
  fi
}

setup_docs_fixture() {
  rm -rf "$DOCS_GATE_ROOT"
  mkdir -p "$DOCS_GATE_ROOT"
  cat > "$DOCS_GATE_ROOT/README.md" <<EOF
# Fixture Project

## Canonical Docs
1. \`docs/projects/$DOCS_GATE_PROJECT/README.md\`
2. \`docs/projects/$DOCS_GATE_PROJECT/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md\`
EOF
  cat > "$DOCS_GATE_ROOT/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md" <<'EOF'
# Safety
Date: 2026-02-24
Status: active
## Objective
baseline
EOF
}

cleanup_docs_fixture() {
  rm -rf "$DOCS_GATE_ROOT"
}

assert_fail_contains() {
  local expected="$1"
  shift
  set +e
  local output
  output="$("$@" 2>&1)"
  local rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    echo "$output"
    die "expected command to fail"
  fi
  if [[ "$output" != *"$expected"* ]]; then
    echo "$output"
    die "expected output to contain '$expected'"
  fi
}
