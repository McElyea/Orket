from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.result_error_invariants import (
    result_error_invariant_contract_snapshot,
    validate_result_error_invariant,
    validate_result_error_invariant_contract,
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
    parser = argparse.ArgumentParser(description="Check result-to-error invariant contract and behavior.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_result_error_invariants() -> dict[str, Any]:
    contract = result_error_invariant_contract_snapshot()
    try:
        forbidden_statuses = list(validate_result_error_invariant_contract(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    behavior_cases = (
        {
            "case_id": "done_without_failure_is_valid",
            "status": "done",
            "failure_class": "",
            "failure_reason": "",
            "expect_ok": True,
        },
        {
            "case_id": "done_with_failure_is_rejected",
            "status": "done",
            "failure_class": "ExecutionFailed",
            "failure_reason": "",
            "expect_ok": False,
            "expected_error": "E_RESULT_ERROR_INVARIANT:done_must_not_have_failure",
        },
        {
            "case_id": "running_with_failure_is_rejected",
            "status": "running",
            "failure_class": "",
            "failure_reason": "should not fail",
            "expect_ok": False,
            "expected_error": "E_RESULT_ERROR_INVARIANT:running_must_not_have_failure",
        },
        {
            "case_id": "failed_with_failure_reason_is_valid",
            "status": "failed",
            "failure_class": "ExecutionFailed",
            "failure_reason": "boom",
            "expect_ok": True,
        },
    )

    checks: list[dict[str, Any]] = []
    for case in behavior_cases:
        expected_error = str(case.get("expected_error") or "").strip()
        try:
            resolved_status = validate_result_error_invariant(
                status=str(case.get("status") or ""),
                failure_class=str(case.get("failure_class") or ""),
                failure_reason=str(case.get("failure_reason") or ""),
            )
        except ValueError as exc:
            observed_error = str(exc)
            checks.append(
                {
                    "check": str(case["case_id"]),
                    "ok": not bool(case.get("expect_ok")) and observed_error == expected_error,
                    "observed_error": observed_error,
                }
            )
            continue

        checks.append(
            {
                "check": str(case["case_id"]),
                "ok": bool(case.get("expect_ok")),
                "resolved_status": resolved_status,
            }
        )

    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "forbidden_status_count": len(forbidden_statuses),
        "behavior_case_count": len(checks),
        "checks": checks,
        "contract": contract,
    }


def check_result_error_invariants(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_result_error_invariants()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_result_error_invariants(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
