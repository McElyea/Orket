#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.trusted_terraform_plan_decision_contract import (
    PROOF_RESULTS_ROOT,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
    now_utc_iso,
    relative_to_repo,
)
from scripts.proof.run_trusted_terraform_plan_decision_runtime_smoke import RUNTIME_SMOKE_SCHEMA_VERSION

READINESS_SCHEMA_VERSION = "trusted_terraform_plan_decision_publication_readiness.v1"
DEFAULT_FOUNDATION_INPUT = PROOF_RESULTS_ROOT / "trusted_run_proof_foundation.json"
DEFAULT_CAMPAIGN_INPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_witness_verification.json"
DEFAULT_OFFLINE_INPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_offline_verifier.json"
DEFAULT_RUNTIME_INPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_live_runtime.json"
DEFAULT_READINESS_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_publication_readiness.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Terraform governed-proof publication readiness without widening publication.")
    parser.add_argument("--foundation-input", default=str(DEFAULT_FOUNDATION_INPUT))
    parser.add_argument("--campaign-input", default=str(DEFAULT_CAMPAIGN_INPUT))
    parser.add_argument("--offline-input", default=str(DEFAULT_OFFLINE_INPUT))
    parser.add_argument("--runtime-input", default=str(DEFAULT_RUNTIME_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_READINESS_OUTPUT))
    parser.add_argument("--json", action="store_true", help="Print the persisted readiness report.")
    return parser.parse_args(argv)


def build_publication_readiness_report(
    *,
    foundation_input: Path,
    campaign_input: Path,
    offline_input: Path,
    runtime_input: Path,
) -> dict[str, Any]:
    checks = [
        _foundation_check(foundation_input),
        _campaign_check(campaign_input),
        _offline_check(offline_input),
        _runtime_check(runtime_input),
    ]
    blocking_reasons = [reason for check in checks for reason in check["blocking_reasons"]]
    environment_blockers = [reason for reason in blocking_reasons if reason.startswith("runtime_environment_blocker")]
    ready = not blocking_reasons
    observed_result = "success" if ready else ("environment blocker" if environment_blockers else "failure")
    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "mixed",
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "observed_path": "primary" if ready else "blocked",
        "observed_result": observed_result,
        "publication_decision": "ready_for_publication_boundary_update" if ready else "blocked",
        "public_trust_slice_action": "same_change_boundary_update_required" if ready else "do_not_widen_public_trust_slice",
        "claim_tier_ceiling": "verdict_deterministic" if ready else "internal_only",
        "required_checks": [check["id"] for check in checks],
        "passed_checks": [check["id"] for check in checks if check["status"] == "pass"],
        "failed_checks": [check for check in checks if check["status"] != "pass"],
        "blocking_reasons": blocking_reasons,
        "input_refs": {
            "proof_foundation": relative_to_repo(foundation_input),
            "campaign": relative_to_repo(campaign_input),
            "offline_claim": relative_to_repo(offline_input),
            "provider_backed_runtime": relative_to_repo(runtime_input),
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = build_publication_readiness_report(
        foundation_input=Path(str(args.foundation_input)).resolve(),
        campaign_input=Path(str(args.campaign_input)).resolve(),
        offline_input=Path(str(args.offline_input)).resolve(),
        runtime_input=Path(str(args.runtime_input)).resolve(),
    )
    output = Path(str(args.output)).resolve()
    persisted = write_payload_with_diff_ledger(output, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"publication_decision={persisted.get('publication_decision')}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("publication_decision") == "ready_for_publication_boundary_update" else 1


def _foundation_check(path: Path) -> dict[str, Any]:
    payload, error = _load_json(path)
    if error:
        return _check("proof_foundation_success", path, "fail", [error])
    targets = payload.get("foundation_targets") if isinstance(payload.get("foundation_targets"), list) else []
    passed = (
        payload.get("schema_version") == "trusted_run_proof_foundation.v1"
        and payload.get("observed_result") == "success"
        and len(targets) == 6
        and all(isinstance(item, dict) and item.get("status") == "pass" for item in targets)
    )
    return _check("proof_foundation_success", path, "pass" if passed else "fail", [] if passed else ["proof_foundation_not_successful"])


def _campaign_check(path: Path) -> dict[str, Any]:
    payload, error = _load_json(path)
    if error:
        return _check("terraform_campaign_verdict_deterministic", path, "fail", [error])
    passed = (
        payload.get("schema_version") == "trusted_run_witness_report.v1"
        and payload.get("compare_scope") == TRUSTED_TERRAFORM_COMPARE_SCOPE
        and payload.get("observed_result") == "success"
        and payload.get("claim_tier") == "verdict_deterministic"
        and int(payload.get("run_count") or 0) >= 2
    )
    return _check("terraform_campaign_verdict_deterministic", path, "pass" if passed else "fail", [] if passed else ["terraform_campaign_not_publication_ready"])


def _offline_check(path: Path) -> dict[str, Any]:
    payload, error = _load_json(path)
    if error:
        return _check("terraform_offline_claim_allowed", path, "fail", [error])
    passed = (
        payload.get("schema_version") == "offline_trusted_run_verifier.v1"
        and payload.get("compare_scope") == TRUSTED_TERRAFORM_COMPARE_SCOPE
        and payload.get("observed_result") == "success"
        and payload.get("claim_status") == "allowed"
        and payload.get("claim_tier") == "verdict_deterministic"
    )
    return _check("terraform_offline_claim_allowed", path, "pass" if passed else "fail", [] if passed else ["terraform_offline_claim_not_allowed"])


def _runtime_check(path: Path) -> dict[str, Any]:
    payload, error = _load_json(path)
    if error:
        return _check("provider_backed_governed_runtime_success", path, "fail", [error])
    if payload.get("observed_result") == "environment blocker":
        return _check("provider_backed_governed_runtime_success", path, "blocked", [f"runtime_environment_blocker:{payload.get('reason') or 'unknown'}"])
    passed = (
        payload.get("schema_version") == RUNTIME_SMOKE_SCHEMA_VERSION
        and payload.get("compare_scope") == TRUSTED_TERRAFORM_COMPARE_SCOPE
        and payload.get("observed_result") == "success"
        and payload.get("execution_status") in {"success", "degraded"}
        and bool(str(payload.get("witness_bundle_ref") or "").strip())
        and _nested_result(payload, "witness_report") == "success"
    )
    return _check("provider_backed_governed_runtime_success", path, "pass" if passed else "fail", [] if passed else ["provider_backed_governed_runtime_not_successful"])


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, f"missing_input:{relative_to_repo(path)}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid_json:{relative_to_repo(path)}:{exc.msg}"
    if not isinstance(payload, dict):
        return {}, f"json_object_required:{relative_to_repo(path)}"
    payload.pop("diff_ledger", None)
    return payload, ""


def _check(check_id: str, path: Path, status: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "input_ref": relative_to_repo(path),
        "blocking_reasons": reasons,
    }


def _nested_result(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return str(value.get("observed_result") or "") if isinstance(value, dict) else ""


if __name__ == "__main__":
    raise SystemExit(main())
