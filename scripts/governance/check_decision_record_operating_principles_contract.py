from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.decision_record_operating_principles_contract import (
    decision_record_operating_principles_contract_snapshot,
    validate_decision_record_operating_principles_contract,
)

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import importlib.util

    helper_path = Path(__file__).resolve().parents[1] / "common" / "rerun_diff_ledger.py"
    spec = importlib.util.spec_from_file_location("rerun_diff_ledger", helper_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"E_DIFF_LEDGER_HELPER_LOAD_FAILED:{helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_payload_with_diff_ledger = module.write_payload_with_diff_ledger


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check decision-record and operating-principles contract docs.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_decision_record_operating_principles_contract(*, workspace: Path) -> dict[str, Any]:
    contract = decision_record_operating_principles_contract_snapshot()
    try:
        check_ids = list(validate_decision_record_operating_principles_contract(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    check_map = {str(row["check_id"]): row for row in contract.get("checks", []) if isinstance(row, dict)}
    checks: list[dict[str, Any]] = []
    for check_id in check_ids:
        row = check_map[check_id]
        relative_path = Path(str(row.get("relative_path") or ""))
        target_path = (workspace / relative_path).resolve()
        required_headings = [str(token).strip() for token in row.get("required_headings", []) if str(token).strip()]
        if not target_path.exists():
            checks.append(
                {
                    "check": check_id,
                    "ok": False,
                    "missing_file": str(relative_path),
                }
            )
            continue
        try:
            content = target_path.read_text(encoding="utf-8")
        except OSError as exc:
            checks.append(
                {
                    "check": check_id,
                    "ok": False,
                    "error": str(exc),
                }
            )
            continue
        missing_headings = [heading for heading in required_headings if heading not in content]
        checks.append(
            {
                "check": check_id,
                "ok": not missing_headings,
                "missing_headings": missing_headings,
            }
        )

    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "check_count": len(check_ids),
        "checks": checks,
        "contract": contract,
    }


def check_decision_record_operating_principles_contract(
    *,
    workspace: Path,
    out_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = evaluate_decision_record_operating_principles_contract(workspace=workspace)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_decision_record_operating_principles_contract(
        workspace=REPO_ROOT,
        out_path=out_path,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
