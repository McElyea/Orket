from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


_LAYER_PATTERN = re.compile(r"layer\s*:\s*(unit|contract|integration|live_truth)", re.IGNORECASE)
_TEST_DEF_PATTERN = re.compile(r"^\s*(?:async\s+def|def)\s+(test_[a-zA-Z0-9_]+)\s*\(")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enforce test taxonomy labels on test functions.")
    parser.add_argument("--root", default="tests", help="Test root directory to scan.")
    parser.add_argument("--strict", action="store_true", help="Fail when unlabeled tests are found.")
    return parser.parse_args(argv)


def _scan_test_file(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        match = _TEST_DEF_PATTERN.match(line)
        if not match:
            continue
        test_name = str(match.group(1))
        start = max(0, index - 4)
        context = "\n".join(lines[start:index])
        layer_match = _LAYER_PATTERN.search(context)
        layer = str(layer_match.group(1)).lower() if layer_match else ""
        rows.append(
            {
                "file": str(path),
                "line": index,
                "test_name": test_name,
                "layer": layer or None,
            }
        )
    return rows


def evaluate_test_taxonomy(*, root: Path) -> dict[str, Any]:
    if not root.exists():
        raise ValueError(f"E_TEST_TAXONOMY_ROOT_MISSING:{root}")
    tests: list[dict[str, Any]] = []
    for path in sorted(root.rglob("test_*.py")):
        tests.extend(_scan_test_file(path))
    missing = [row for row in tests if not row.get("layer")]
    by_layer: dict[str, int] = {}
    for row in tests:
        layer = str(row.get("layer") or "unlabeled")
        by_layer[layer] = by_layer.get(layer, 0) + 1
    return {
        "schema_version": "test_taxonomy_report.v1",
        "tests_total": len(tests),
        "missing_layer_total": len(missing),
        "by_layer": by_layer,
        "missing_layers": missing,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = evaluate_test_taxonomy(root=Path(args.root).resolve())
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    if bool(args.strict) and int(payload.get("missing_layer_total") or 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
