from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.error_codes import error_family_for_leaf


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize local prompting failure families.")
    parser.add_argument("--input", action="append", required=True, help="Input conformance JSON report path.")
    parser.add_argument(
        "--out",
        default="benchmarks/results/protocol/local_prompting/failure_summary.json",
        help="Canonical summary output path.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any failures are present.")
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _merge_failures(inputs: list[dict[str, Any]]) -> dict[str, Any]:
    family_counts: dict[str, int] = {}
    report_summaries: list[dict[str, Any]] = []
    for payload in inputs:
        families = payload.get("failure_families")
        summary = {
            "schema_version": str(payload.get("schema_version") or ""),
            "profile_id": str(payload.get("profile_id") or ""),
            "task_class": str(payload.get("task_class") or ""),
            "total_cases": int(payload.get("total_cases") or 0),
            "pass_cases": int(payload.get("pass_cases") or 0),
        }
        report_summaries.append(summary)
        if not isinstance(families, dict):
            continue
        for family, count in families.items():
            key = error_family_for_leaf(str(family)) or str(family)
            family_counts[key] = family_counts.get(key, 0) + int(count or 0)
    total_failures = sum(family_counts.values())
    return {
        "schema_version": "local_prompting_failure_summary.v1",
        "total_failures": total_failures,
        "family_counts": {key: family_counts[key] for key in sorted(family_counts)},
        "reports": report_summaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payloads = [_load_json(Path(raw).resolve()) for raw in list(args.input or [])]
    summary = _merge_failures(payloads)
    write_payload_with_diff_ledger(Path(str(args.out)).resolve(), summary)
    if bool(args.strict) and int(summary.get("total_failures", 0)) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
