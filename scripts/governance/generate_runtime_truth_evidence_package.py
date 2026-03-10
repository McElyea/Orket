from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.evidence_package_generator_contract import (
    evidence_package_generator_contract_snapshot,
)
from orket.runtime.runtime_truth_drift_checker import runtime_truth_contract_drift_report
from scripts.governance.check_interface_freeze_windows import evaluate_interface_freeze_windows
from scripts.governance.check_non_fatal_error_budget import evaluate_non_fatal_error_budget
from scripts.governance.check_promotion_rollback_criteria import evaluate_promotion_rollback_criteria
from scripts.governance.check_release_confidence_scorecard import evaluate_release_confidence_scorecard
from scripts.governance.run_runtime_truth_acceptance_gate import (
    REQUIRED_RUNTIME_CONTRACT_FILES,
    evaluate_runtime_truth_acceptance_gate,
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
    parser = argparse.ArgumentParser(description="Generate runtime truth evidence package.")
    parser.add_argument("--workspace", default=".", help="Workspace root.")
    parser.add_argument("--run-id", default="", help="Optional run id for artifact inventory.")
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    return parser.parse_args(argv)


def _default_out_path(workspace: Path) -> Path:
    return workspace / "observability" / "runtime_truth_evidence_package.json"


def _runtime_contract_inventory(*, workspace: Path, run_id: str) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return {
            "runtime_contracts_dir": "",
            "files_present": [],
            "required_files_missing": [],
        }

    contracts_dir = workspace / "observability" / normalized_run_id / "runtime_contracts"
    files_present = (
        sorted(path.name for path in contracts_dir.glob("*.json") if path.is_file())
        if contracts_dir.exists()
        else []
    )
    required_files_missing = [
        filename for filename in REQUIRED_RUNTIME_CONTRACT_FILES if not (contracts_dir / filename).exists()
    ]
    return {
        "runtime_contracts_dir": str(contracts_dir),
        "files_present": files_present,
        "required_files_missing": required_files_missing,
    }


def build_runtime_truth_evidence_package(
    *,
    workspace: Path,
    run_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    resolved_workspace = workspace.resolve()
    normalized_run_id = str(run_id or "").strip()
    timestamp = (now or datetime.now(UTC)).isoformat()
    package_id = f"runtime-truth-evidence::{normalized_run_id or 'no-run-id'}::{timestamp}"

    acceptance_gate_payload = evaluate_runtime_truth_acceptance_gate(
        workspace=resolved_workspace,
        run_id=normalized_run_id,
        check_drift=True,
    )
    drift_report = dict(acceptance_gate_payload.get("details", {}).get("drift_report") or runtime_truth_contract_drift_report())
    scorecard_payload = evaluate_release_confidence_scorecard()
    non_fatal_budget_payload = evaluate_non_fatal_error_budget()
    freeze_windows_payload = evaluate_interface_freeze_windows()
    rollback_payload = evaluate_promotion_rollback_criteria()
    artifact_inventory = _runtime_contract_inventory(workspace=resolved_workspace, run_id=normalized_run_id)

    promotion_recommendation = "eligible"
    if not bool(acceptance_gate_payload.get("ok")):
        promotion_recommendation = "blocked"
    elif not bool(scorecard_payload.get("ok")):
        promotion_recommendation = "manual_review"

    return {
        "schema_version": "runtime_truth_evidence_package.v1",
        "package_id": package_id,
        "generated_at": timestamp,
        "workspace_root": str(resolved_workspace),
        "run_id": normalized_run_id,
        "generator_version": "1.0",
        "gate_summary": {
            "ok": bool(acceptance_gate_payload.get("ok")),
            "failures": list(acceptance_gate_payload.get("failures", [])),
        },
        "drift_report": drift_report,
        "release_confidence_scorecard": scorecard_payload,
        "non_fatal_error_budget": non_fatal_budget_payload,
        "interface_freeze_windows": freeze_windows_payload,
        "promotion_rollback_criteria": rollback_payload,
        "artifact_inventory": artifact_inventory,
        "decision_record": {
            "promotion_recommendation": promotion_recommendation,
            "required_operator_action": (
                "operator_signoff_required" if promotion_recommendation == "eligible" else "resolve_gate_failures"
            ),
        },
        "generator_contract": evidence_package_generator_contract_snapshot(),
    }


def generate_runtime_truth_evidence_package(
    *,
    workspace: Path,
    run_id: str,
    out_path: Path | None = None,
    now: datetime | None = None,
) -> tuple[int, dict[str, Any], Path]:
    payload = build_runtime_truth_evidence_package(
        workspace=workspace,
        run_id=run_id,
        now=now,
    )
    resolved_out_path = (out_path or _default_out_path(workspace.resolve())).resolve()
    resolved_out_path.parent.mkdir(parents=True, exist_ok=True)
    write_payload_with_diff_ledger(resolved_out_path, payload)
    return (0 if bool(payload.get("gate_summary", {}).get("ok")) else 1), payload, resolved_out_path


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    workspace = Path(args.workspace).resolve()
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload, resolved_out_path = generate_runtime_truth_evidence_package(
        workspace=workspace,
        run_id=str(args.run_id or "").strip(),
        out_path=out_path,
    )
    result = {
        **payload,
        "out_path": str(resolved_out_path),
    }
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
