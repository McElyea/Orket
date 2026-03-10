from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.runtime_truth_contracts import (
    degradation_taxonomy_snapshot,
    fail_behavior_registry_snapshot,
    runtime_status_vocabulary_snapshot,
    validate_degradation_taxonomy_contract,
    validate_fail_behavior_registry_contract,
    validate_runtime_status_vocabulary_contract,
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
    parser = argparse.ArgumentParser(description="Check runtime truth foundation contracts.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_runtime_truth_foundation_contracts() -> dict[str, Any]:
    status_snapshot = runtime_status_vocabulary_snapshot()
    degradation_snapshot = degradation_taxonomy_snapshot()
    fail_behavior_snapshot = fail_behavior_registry_snapshot()

    checks: list[dict[str, Any]] = []
    try:
        terms = list(validate_runtime_status_vocabulary_contract(status_snapshot))
        checks.append(
            {
                "check": "runtime_status_vocabulary_contract_valid",
                "ok": True,
                "count": len(terms),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "runtime_status_vocabulary_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        levels = list(validate_degradation_taxonomy_contract(degradation_snapshot))
        checks.append(
            {
                "check": "degradation_taxonomy_contract_valid",
                "ok": True,
                "count": len(levels),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "degradation_taxonomy_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        subsystems = list(validate_fail_behavior_registry_contract(fail_behavior_snapshot))
        checks.append(
            {
                "check": "fail_behavior_registry_contract_valid",
                "ok": True,
                "count": len(subsystems),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "fail_behavior_registry_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "checks": checks,
        "runtime_status_vocabulary_snapshot": status_snapshot,
        "degradation_taxonomy_snapshot": degradation_snapshot,
        "fail_behavior_registry_snapshot": fail_behavior_snapshot,
    }


def check_runtime_truth_foundation_contracts(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_runtime_truth_foundation_contracts()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_runtime_truth_foundation_contracts(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
