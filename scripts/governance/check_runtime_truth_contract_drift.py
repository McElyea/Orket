from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orket.runtime.runtime_truth_drift_checker import runtime_truth_contract_drift_report

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import sys

    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


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
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or [])
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_runtime_truth_contract_drift(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
