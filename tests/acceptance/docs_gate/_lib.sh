#!/usr/bin/env bash
set -euo pipefail

DOCS_LINT_CMD=${DOCS_LINT_CMD:-"python scripts/docs_lint.py --project core-pillars"}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

ensure_clean_tree() {
  if ! git diff --quiet || ! git diff --cached --quiet; then
    die "git working tree must be clean before running acceptance tests"
  fi
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

