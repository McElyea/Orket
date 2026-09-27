"""Classify actual pytest items, including inherited and parameter-specific marks."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.common.git_inventory import GitInventoryError
    from scripts.governance.quality_scan_inventory import git_visible_python_files
except ModuleNotFoundError:  # Native script invocation outside an installed source tree.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.common.git_inventory import GitInventoryError
    from scripts.governance.quality_scan_inventory import git_visible_python_files


CANONICAL_LAYERS = frozenset({"unit", "contract", "integration", "end_to_end"})


class _TaxonomyCollector:
    def __init__(self) -> None:
        self.tests: dict[str, dict[str, Any]] = {}
        self.errors: list[str] = []

    def _record(self, items: list[Any]) -> None:
        for item in items:
            layers = sorted({mark.name for mark in item.iter_markers() if mark.name in CANONICAL_LAYERS})
            self.tests[item.nodeid] = {
                "file": str(item.path),
                "line": item.location[1] + 1,
                "test_name": item.name,
                "nodeid": item.nodeid,
                "layers": layers,
                "layer": layers[0] if len(layers) == 1 else None,
            }

    def pytest_collection_finish(self, session: Any) -> None:
        self._record(session.items)

    def pytest_deselected(self, items: list[Any]) -> None:
        # Collection hooks cannot hide unclassified items by deselecting them.
        self._record(items)

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self.errors.append(str(report.longrepr))


def _collect(root: Path) -> dict[str, Any]:
    import pytest

    collector = _TaxonomyCollector()
    output = io.StringIO()
    try:
        targets = [str(path) for path in git_visible_python_files([root]) if path.name.startswith("test_")]
    except (GitInventoryError, OSError) as exc:
        targets = []
        collector.errors.append(f"E_TEST_TAXONOMY_INVENTORY:{exc}")
    code = 5
    if targets:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = int(pytest.main(
                ["--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider", *targets],
                plugins=[collector],
            ))
    rows = sorted(collector.tests.values(), key=lambda row: row["nodeid"])
    missing = [row for row in rows if not row["layers"]]
    invalid = [row for row in rows if len(row["layers"]) > 1]
    counts = Counter(row["layer"] or ("invalid" if row["layers"] else "unlabeled") for row in rows)
    return {
        "schema_version": "test_taxonomy_report.v2",
        "classification_source": "pytest_collection",
        "ok": code == 0 and not collector.errors and not missing and not invalid,
        "tests_total": len(rows),
        "missing_layer_total": len(missing),
        "invalid_layer_total": len(invalid),
        "by_layer": dict(sorted(counts.items())),
        "missing_layers": missing,
        "invalid_layers": invalid,
        "collection_exit_code": code,
        "collection_errors": collector.errors,
        "collection_output": output.getvalue() if code != 0 else "",
    }


def evaluate_test_taxonomy(*, root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.exists():
        raise ValueError(f"E_TEST_TAXONOMY_ROOT_MISSING:{root}")
    # A fresh interpreter preserves pytest's import/marker semantics without
    # contaminating a caller's already-collected test modules or plugin state.
    environment = dict(os.environ, PYTEST_ADDOPTS="", PYTHONDONTWRITEBYTECODE="1")
    child = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--collect", "--root", str(root)],
        capture_output=True, text=True, encoding="utf-8", env=environment, check=False,
    )
    if child.returncode:
        raise RuntimeError(f"E_TEST_TAXONOMY_COLLECTION_PROCESS:{child.returncode}:{child.stderr}")
    return json.loads(child.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce canonical pytest layer markers on collected test items.")
    parser.add_argument("--root", default="tests", help="Test root directory or test file to collect.")
    parser.add_argument("--strict", action="store_true", help="Fail when items have missing or conflicting layers.")
    parser.add_argument("--collect", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    payload = _collect(Path(args.root)) if args.collect else evaluate_test_taxonomy(root=Path(args.root))
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    if args.collect:
        return 0  # The report retains pytest's exit status, including incomplete collection.
    if payload["collection_exit_code"] != 0 or payload["collection_errors"]:
        return 1
    return int(bool(args.strict) and not payload["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
