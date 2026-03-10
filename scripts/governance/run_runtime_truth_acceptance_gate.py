from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orket.runtime.runtime_truth_drift_checker import runtime_truth_contract_drift_report


REQUIRED_RUNTIME_CONTRACT_FILES: tuple[str, ...] = (
    "run_phase_contract.json",
    "runtime_status_vocabulary.json",
    "degradation_taxonomy.json",
    "fail_behavior_registry.json",
    "provider_truth_table.json",
    "state_transition_registry.json",
    "timeout_semantics_contract.json",
    "streaming_semantics_contract.json",
    "runtime_truth_contract_drift_report.json",
    "runtime_truth_trace_ids.json",
    "runtime_invariant_registry.json",
    "runtime_config_ownership_map.json",
    "unknown_input_policy.json",
    "clock_time_authority_policy.json",
    "capability_fallback_hierarchy.json",
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run runtime truth acceptance gate checks.")
    parser.add_argument("--workspace", default=".", help="Workspace root containing observability/runs.")
    parser.add_argument("--run-id", default="", help="Optional run id for runtime contract artifact checks.")
    parser.add_argument(
        "--skip-drift-check",
        action="store_true",
        help="Skip runtime truth drift checker.",
    )
    return parser.parse_args(argv)


def _runtime_contracts_dir(workspace: Path, run_id: str) -> Path:
    return workspace / "observability" / str(run_id).strip() / "runtime_contracts"


def evaluate_runtime_truth_acceptance_gate(
    *,
    workspace: Path,
    run_id: str,
    check_drift: bool,
) -> dict[str, Any]:
    failures: list[str] = []
    details: dict[str, Any] = {}

    if check_drift:
        drift = runtime_truth_contract_drift_report()
        details["drift_report"] = drift
        if not bool(drift.get("ok")):
            failures.append("runtime_truth_contract_drift")

    normalized_run_id = str(run_id or "").strip()
    if normalized_run_id:
        contracts_dir = _runtime_contracts_dir(workspace, normalized_run_id)
        missing_files: list[str] = []
        invalid_json_files: list[str] = []
        for filename in REQUIRED_RUNTIME_CONTRACT_FILES:
            path = contracts_dir / filename
            if not path.exists():
                missing_files.append(filename)
                continue
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                invalid_json_files.append(filename)
                continue
            if not isinstance(parsed, dict):
                invalid_json_files.append(filename)
        details["runtime_contracts_dir"] = str(contracts_dir)
        details["missing_files"] = missing_files
        details["invalid_json_files"] = invalid_json_files
        if missing_files:
            failures.append("runtime_contract_files_missing")
        if invalid_json_files:
            failures.append("runtime_contract_files_invalid_json")

    return {
        "schema_version": "runtime_truth_acceptance_gate.v1",
        "ok": not failures,
        "failures": failures,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or [])
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=Path(args.workspace).resolve(),
        run_id=str(args.run_id or "").strip(),
        check_drift=not bool(args.skip_drift_check),
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
