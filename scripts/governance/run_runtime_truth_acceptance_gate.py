from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.runtime_truth_drift_checker import runtime_truth_contract_drift_report
from scripts.governance.check_noop_critical_paths import (
    DEFAULT_SCAN_ROOTS as DEFAULT_NOOP_SCAN_ROOTS,
    evaluate_noop_critical_paths,
)
from scripts.governance.check_environment_parity_checklist import evaluate_environment_parity_checklist
from scripts.governance.check_interrupt_semantics_policy import evaluate_interrupt_semantics_policy
from scripts.governance.check_model_profile_bios import evaluate_model_profile_bios
from scripts.governance.check_runtime_boundary_audit_checklist import evaluate_runtime_boundary_audit_checklist
from scripts.governance.check_retry_classification_policy import evaluate_retry_classification_policy
from scripts.governance.check_structured_warning_policy import evaluate_structured_warning_policy
from scripts.governance.check_unreachable_branches import (
    DEFAULT_SCAN_ROOTS as DEFAULT_UNREACHABLE_SCAN_ROOTS,
    evaluate_unreachable_branches,
)


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
    "model_profile_bios.json",
    "interrupt_semantics_policy.json",
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
    parser.add_argument(
        "--skip-unreachable-branch-check",
        action="store_true",
        help="Skip unreachable-branch detector for critical roots.",
    )
    parser.add_argument(
        "--skip-noop-critical-path-check",
        action="store_true",
        help="Skip no-op critical-path detector for critical roots.",
    )
    parser.add_argument(
        "--skip-environment-parity-check",
        action="store_true",
        help="Skip environment parity checklist.",
    )
    parser.add_argument(
        "--skip-warning-policy-check",
        action="store_true",
        help="Skip structured warning policy contract check.",
    )
    parser.add_argument(
        "--skip-retry-policy-check",
        action="store_true",
        help="Skip retry classification policy contract check.",
    )
    parser.add_argument(
        "--skip-boundary-audit-check",
        action="store_true",
        help="Skip runtime boundary audit checklist contract check.",
    )
    parser.add_argument(
        "--skip-model-profile-bios-check",
        action="store_true",
        help="Skip model profile BIOS contract check.",
    )
    parser.add_argument(
        "--skip-interrupt-policy-check",
        action="store_true",
        help="Skip interrupt semantics policy contract check.",
    )
    return parser.parse_args(argv)


def _runtime_contracts_dir(workspace: Path, run_id: str) -> Path:
    return workspace / "observability" / str(run_id).strip() / "runtime_contracts"


def evaluate_runtime_truth_acceptance_gate(
    *,
    workspace: Path,
    run_id: str,
    check_drift: bool,
    check_unreachable_branches: bool = True,
    check_noop_critical_paths: bool = True,
    check_environment_parity: bool = True,
    check_warning_policy: bool = True,
    check_retry_policy: bool = True,
    check_boundary_audit: bool = True,
    check_model_profile_bios: bool = True,
    check_interrupt_policy: bool = True,
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

    if check_unreachable_branches:
        roots = [workspace / path for path in DEFAULT_UNREACHABLE_SCAN_ROOTS]
        unreachable_payload = evaluate_unreachable_branches(roots=roots)
        details["unreachable_branch_check"] = {
            "ok": bool(unreachable_payload.get("ok")),
            "findings_count": len(unreachable_payload.get("findings", [])),
            "parse_errors_count": len(unreachable_payload.get("parse_errors", [])),
        }
        if not bool(unreachable_payload.get("ok")):
            failures.append("unreachable_branch_check_failed")

    if check_noop_critical_paths:
        roots = [workspace / path for path in DEFAULT_NOOP_SCAN_ROOTS]
        noop_payload = evaluate_noop_critical_paths(roots=roots)
        details["noop_critical_path_check"] = {
            "ok": bool(noop_payload.get("ok")),
            "findings_count": len(noop_payload.get("findings", [])),
            "parse_errors_count": len(noop_payload.get("parse_errors", [])),
        }
        if not bool(noop_payload.get("ok")):
            failures.append("noop_critical_path_check_failed")

    if check_environment_parity:
        parity_payload = evaluate_environment_parity_checklist(environment=None, required_keys=[])
        failed_checks = [row for row in parity_payload.get("checks", []) if not bool((row or {}).get("ok"))]
        details["environment_parity_check"] = {
            "ok": bool(parity_payload.get("ok")),
            "failed_check_count": len(failed_checks),
        }
        if not bool(parity_payload.get("ok")):
            failures.append("environment_parity_check_failed")

    if check_warning_policy:
        warning_policy_payload = evaluate_structured_warning_policy()
        details["structured_warning_policy_check"] = {
            "ok": bool(warning_policy_payload.get("ok")),
            "warning_count": int(warning_policy_payload.get("warning_count") or 0),
        }
        if not bool(warning_policy_payload.get("ok")):
            failures.append("structured_warning_policy_check_failed")

    if check_retry_policy:
        retry_policy_payload = evaluate_retry_classification_policy()
        details["retry_classification_policy_check"] = {
            "ok": bool(retry_policy_payload.get("ok")),
            "signal_count": int(retry_policy_payload.get("signal_count") or 0),
        }
        if not bool(retry_policy_payload.get("ok")):
            failures.append("retry_classification_policy_check_failed")

    if check_boundary_audit:
        boundary_payload = evaluate_runtime_boundary_audit_checklist(workspace=REPO_ROOT)
        details["runtime_boundary_audit_check"] = {
            "ok": bool(boundary_payload.get("ok")),
            "boundary_count": int(boundary_payload.get("boundary_count") or 0),
        }
        if not bool(boundary_payload.get("ok")):
            failures.append("runtime_boundary_audit_check_failed")

    if check_model_profile_bios:
        bios_payload = evaluate_model_profile_bios()
        details["model_profile_bios_check"] = {
            "ok": bool(bios_payload.get("ok")),
            "profile_count": int(bios_payload.get("profile_count") or 0),
        }
        if not bool(bios_payload.get("ok")):
            failures.append("model_profile_bios_check_failed")

    if check_interrupt_policy:
        interrupt_policy_payload = evaluate_interrupt_semantics_policy()
        details["interrupt_semantics_policy_check"] = {
            "ok": bool(interrupt_policy_payload.get("ok")),
            "surface_count": int(interrupt_policy_payload.get("surface_count") or 0),
        }
        if not bool(interrupt_policy_payload.get("ok")):
            failures.append("interrupt_semantics_policy_check_failed")

    return {
        "schema_version": "runtime_truth_acceptance_gate.v1",
        "ok": not failures,
        "failures": failures,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=Path(args.workspace).resolve(),
        run_id=str(args.run_id or "").strip(),
        check_drift=not bool(args.skip_drift_check),
        check_unreachable_branches=not bool(args.skip_unreachable_branch_check),
        check_noop_critical_paths=not bool(args.skip_noop_critical_path_check),
        check_environment_parity=not bool(args.skip_environment_parity_check),
        check_warning_policy=not bool(args.skip_warning_policy_check),
        check_retry_policy=not bool(args.skip_retry_policy_check),
        check_boundary_audit=not bool(args.skip_boundary_audit_check),
        check_model_profile_bios=not bool(args.skip_model_profile_bios_check),
        check_interrupt_policy=not bool(args.skip_interrupt_policy_check),
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
