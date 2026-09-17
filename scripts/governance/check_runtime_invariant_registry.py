from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orket.runtime.runtime_invariant_registry import runtime_invariant_registry_snapshot
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check runtime invariant registry contract.")
    parser.add_argument(
        "--doc",
        default="",
        help="Optional invariant authority doc path. Defaults to the shipped runtime invariant contract.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_runtime_invariant_registry(*, doc_path: Path | None = None) -> dict[str, Any]:
    try:
        snapshot = (
            runtime_invariant_registry_snapshot(doc_path=doc_path)
            if doc_path is not None
            else runtime_invariant_registry_snapshot()
        )
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
        }

    invariants = [row for row in snapshot.get("invariants", []) if isinstance(row, dict)]
    return {
        "schema_version": "1.0",
        "ok": len(invariants) >= 1,
        "invariant_count": len(invariants),
        "invariant_ids": [str(row.get("invariant_id") or "").strip() for row in invariants],
        "snapshot": snapshot,
    }


def check_runtime_invariant_registry(
    *,
    doc_path: Path | None = None,
    out_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = evaluate_runtime_invariant_registry(doc_path=doc_path)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    doc_path = Path(args.doc).resolve() if str(args.doc or "").strip() else None
    exit_code, payload = check_runtime_invariant_registry(
        doc_path=doc_path,
        out_path=out_path,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
