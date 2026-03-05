from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orket.runtime.protocol_determinism_campaign import compare_protocol_determinism_campaign


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic replay comparisons for a set of protocol run directories.",
    )
    parser.add_argument("--runs-root", required=True, help="Directory containing run folders under runs/<run_id>/")
    parser.add_argument("--run-id", action="append", default=[], help="Optional run id filter (repeatable).")
    parser.add_argument("--baseline-run-id", default="", help="Optional explicit baseline run id.")
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any candidate mismatches baseline.")
    return parser


def _write(payload: dict[str, Any], *, out_path: Path | None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if out_path is None:
        print(text, end="")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    runs_root = Path(str(args.runs_root)).resolve()
    payload = compare_protocol_determinism_campaign(
        runs_root=runs_root,
        run_ids=list(args.run_id or []),
        baseline_run_id=str(args.baseline_run_id or "").strip() or None,
    )
    out_raw = str(args.out or "").strip()
    out_path = Path(out_raw).resolve() if out_raw else None
    _write(payload, out_path=out_path)
    if bool(args.strict) and not bool(payload.get("all_match", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
