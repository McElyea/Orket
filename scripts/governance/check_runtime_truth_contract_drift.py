from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orket.runtime.runtime_truth_drift_checker import runtime_truth_contract_drift_report


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check runtime truth contract drift.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path for the drift report.",
    )
    return parser.parse_args(argv)


def check_runtime_truth_contract_drift(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = runtime_truth_contract_drift_report()
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or [])
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_runtime_truth_contract_drift(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
