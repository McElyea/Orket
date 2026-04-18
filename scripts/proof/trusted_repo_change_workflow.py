from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.trusted_repo_change_contract import (
    APPROVAL_REASON,
    BUNDLE_SCHEMA_VERSION,
    CHANGE_ID,
    CONFIG_ARTIFACT_PATH,
    DEFAULT_BUNDLE_NAME,
    DEFAULT_VALIDATOR_OUTPUT,
    DEFAULT_WORKSPACE_ROOT,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    RESOURCE_ID,
    TRUSTED_REPO_COMPARE_SCOPE,
    WORKFLOW_REQUEST_SCHEMA_VERSION,
    artifact_ref,
    build_contract_verdict,
    expected_config_payload,
    now_utc_iso,
    relative_to_repo,
    stable_json_digest,
    validate_config_artifact,
)
from scripts.proof.trusted_repo_change_verifier import verify_trusted_repo_change_bundle_payload

LIVE_RUN_SCHEMA_VERSION = "trusted_repo_change_live_run.v1"
SCENARIOS = {"approved", "denied", "validator_failure"}


def execute_trusted_repo_change(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    scenario: str = "approved",
    run_index: int = 1,
) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unsupported_trusted_repo_change_scenario:{scenario}")
    context = _execution_context(workspace_root, scenario, run_index)
    before_digest = _file_digest(context["config_path"])
    flow_request = _flow_request(run_id=context["run_id"], session_id=context["session_id"])
    flow_ref = _persist(context["run_root"] / "trusted_repo_change_flow.json", flow_request)
    operator_decision = "denied" if scenario == "denied" else "approved"
    if operator_decision == "approved":
        _write_config(context["config_path"], _config_for_scenario(scenario))
    after_digest = _file_digest(context["config_path"])
    validator = validate_config_artifact(context["config_path"])
    validator_ref = _persist(context["run_root"] / "trusted_repo_config_validator.json", validator)
    write_payload_with_diff_ledger(DEFAULT_VALIDATOR_OUTPUT, validator)
    workflow_result = _workflow_result(scenario=scenario, validator=validator, changed=before_digest != after_digest)
    authority = _authority_lineage(
        run_id=context["run_id"],
        session_id=context["session_id"],
        operator_decision=operator_decision,
        workflow_result=workflow_result,
        flow_request=flow_request,
        validator=validator,
    )
    authority_ref = _persist(context["run_root"] / "trusted_repo_change_run_authority.json", authority)
    bundle = _build_bundle(
        workspace=context["workspace"],
        repo_root=context["repo_root"],
        run_root=context["run_root"],
        run_id=context["run_id"],
        session_id=context["session_id"],
        flow_ref=flow_ref,
        authority_ref=authority_ref,
        validator_ref=validator_ref,
        authority=authority,
        validator=validator,
        config_path=context["config_path"],
    )
    bundle_ref = ""
    report: dict[str, Any] = {}
    if operator_decision == "approved":
        bundle_path = context["run_root"] / DEFAULT_BUNDLE_NAME
        bundle_ref = _persist(bundle_path, bundle)
        report = verify_trusted_repo_change_bundle_payload(bundle, evidence_ref=bundle_ref)
    return _live_payload(
        scenario=scenario,
        workspace=context["workspace"],
        repo_root=context["repo_root"],
        config_path=context["config_path"],
        run_id=context["run_id"],
        session_id=context["session_id"],
        before_digest=before_digest,
        after_digest=after_digest,
        workflow_result=workflow_result,
        flow_ref=flow_ref,
        authority_ref=authority_ref,
        validator_ref=validator_ref,
        bundle_ref=bundle_ref,
        validator=validator,
        bundle=bundle if operator_decision == "approved" else {},
        report=report,
    )


def persist_live_run(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return write_payload_with_diff_ledger(path.resolve(), payload)


def _execution_context(workspace_root: Path, scenario: str, run_index: int) -> dict[str, Any]:
    workspace = workspace_root.resolve()
    session_id = f"trusted-repo-change-{scenario}-{run_index:02d}"
    run_id = f"trusted-repo-run:{session_id}:{CHANGE_ID}:0001"
    run_root = workspace / "runs" / session_id
    config_path = workspace / CONFIG_ARTIFACT_PATH
    _ensure_target_in_workspace(config_path, workspace)
    run_root.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    return {
        "workspace": workspace,
        "repo_root": workspace / "repo",
        "run_root": run_root,
        "config_path": config_path,
        "session_id": session_id,
        "run_id": run_id,
    }


def _flow_request(*, run_id: str, session_id: str) -> dict[str, Any]:
    return {
        "schema_version": WORKFLOW_REQUEST_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "request_id": f"trusted-repo-change-request:{session_id}",
        "run_id": run_id,
        "session_id": session_id,
        "task": "Approve and verify a local fixture repo config change under policy.",
        "change_id": CHANGE_ID,
        "artifact_path": CONFIG_ARTIFACT_PATH,
        "approval_required": True,
        "approval_reason": APPROVAL_REASON,
        "expected_config_digest": stable_json_digest(expected_config_payload()),
    }


def _authority_lineage(
    *,
    run_id: str,
    session_id: str,
    operator_decision: str,
    workflow_result: str,
    flow_request: dict[str, Any],
    validator: dict[str, Any],
) -> dict[str, Any]:
    final_truth_id = f"trusted-repo-final-truth:{run_id}"
    accepted = operator_decision == "approved"
    success = workflow_result == "success"
    return {
        "governed_input": _without_time(flow_request),
        "run": _run_record(run_id, session_id, final_truth_id, success),
        "step": _step_record(run_id, accepted),
        "approval_request": _approval_request(run_id),
        "operator_action": _operator_action(run_id, session_id, operator_decision),
        "checkpoint": _checkpoint(run_id, accepted),
        "resource": _resource(run_id),
        "reservation": _reservation(run_id, session_id),
        "effect_journal": _effect_journal(run_id, accepted, validator),
        "final_truth": _final_truth(final_truth_id, workflow_result),
    }


def _build_bundle(
    *,
    workspace: Path,
    repo_root: Path,
    run_root: Path,
    run_id: str,
    session_id: str,
    flow_ref: str,
    authority_ref: str,
    validator_ref: str,
    authority: dict[str, Any],
    validator: dict[str, Any],
    config_path: Path,
) -> dict[str, Any]:
    control_bundle = {
        "policy_digest": "sha256:trusted-repo-change-policy-v1",
        "configuration_snapshot_ref": f"trusted-repo-config:{run_id}",
        "validator_signature_digest": validator.get("validator_signature_digest"),
    }
    bundle = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": f"trusted-repo-bundle:{run_id}",
        "recorded_at_utc": now_utc_iso(),
        "run_id": run_id,
        "session_id": session_id,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "claim_tier": FALLBACK_CLAIM_TIER,
        "policy_digest": control_bundle["policy_digest"],
        "policy_snapshot_ref": f"trusted-repo-policy:{run_id}",
        "configuration_snapshot_ref": control_bundle["configuration_snapshot_ref"],
        "control_bundle_ref": f"runs/{session_id}/trusted_repo_change_run_authority.json",
        "control_bundle_digest": stable_json_digest(control_bundle),
        "resolution_basis": {"flow_request_ref": flow_ref, "run_authority_ref": authority_ref, "validator_ref": validator_ref},
        "trusted_repo_change_slice": {"change_id": CHANGE_ID, "artifact_path": CONFIG_ARTIFACT_PATH, "repo_root": relative_to_repo(repo_root)},
        "artifact_refs": _artifact_refs(workspace, run_root, config_path),
        "authority_lineage": authority,
        "validator_result": validator,
        "observed_effect": _observed_effect(workspace, config_path),
    }
    bundle["contract_verdict"] = build_contract_verdict(bundle)
    return bundle


def _live_payload(
    *,
    scenario: str,
    workspace: Path,
    repo_root: Path,
    config_path: Path,
    run_id: str,
    session_id: str,
    before_digest: str,
    after_digest: str,
    workflow_result: str,
    flow_ref: str,
    authority_ref: str,
    validator_ref: str,
    bundle_ref: str,
    validator: dict[str, Any],
    bundle: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    proof_ok = _proof_observed_success(scenario=scenario, workflow_result=workflow_result, before_digest=before_digest, after_digest=after_digest, report=report)
    return {
        "schema_version": LIVE_RUN_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live",
        "scenario": scenario,
        "observed_path": "primary" if proof_ok else "blocked",
        "observed_result": "success" if proof_ok else "failure",
        "workflow_result": workflow_result,
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "run_id": run_id,
        "session_id": session_id,
        "workspace_root": relative_to_repo(workspace),
        "repo_root": relative_to_repo(repo_root),
        "artifact_path": CONFIG_ARTIFACT_PATH,
        "artifact_ref": relative_to_repo(config_path) if config_path.exists() else "",
        "artifact_digest_before": before_digest,
        "artifact_digest_after": after_digest,
        "artifact_changed": before_digest != after_digest,
        "flow_request_ref": flow_ref,
        "run_authority_ref": authority_ref,
        "validator_ref": validator_ref,
        "witness_bundle_ref": bundle_ref,
        "validator_result": validator,
        "witness_report": report,
        "bundle_id": str(bundle.get("bundle_id") or ""),
    }


def _proof_observed_success(*, scenario: str, workflow_result: str, before_digest: str, after_digest: str, report: dict[str, Any]) -> bool:
    if scenario == "approved":
        return workflow_result == "success" and report.get("observed_result") == "success"
    if scenario == "denied":
        return workflow_result == "blocked" and before_digest == after_digest
    if scenario == "validator_failure":
        return workflow_result == "failure" and report.get("observed_result") == "failure"
    return False


def _workflow_result(*, scenario: str, validator: dict[str, Any], changed: bool) -> str:
    if scenario == "denied":
        return "blocked"
    if scenario == "approved" and validator.get("validation_result") == "pass":
        return "success"
    return "failure"


def _config_for_scenario(scenario: str) -> dict[str, Any]:
    payload = expected_config_payload()
    if scenario == "validator_failure":
        payload["risk_class"] = "high"
    return payload


def _write_config(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _artifact_refs(workspace: Path, run_root: Path, config_path: Path) -> list[dict[str, Any]]:
    return [
        artifact_ref("run_authority", run_root / "trusted_repo_change_run_authority.json", workspace),
        artifact_ref("validator_report", run_root / "trusted_repo_config_validator.json", workspace),
        artifact_ref("output_artifact", config_path, workspace, ref_path=CONFIG_ARTIFACT_PATH),
    ]


def _observed_effect(workspace: Path, config_path: Path) -> dict[str, Any]:
    exists = config_path.exists()
    return {
        "expected_output_artifact_path": CONFIG_ARTIFACT_PATH,
        "actual_output_artifact_path": CONFIG_ARTIFACT_PATH if exists else "",
        "output_exists": exists,
        "artifact_digest": _file_digest(config_path),
        "forbidden_mutations": _forbidden_mutations(workspace),
    }


def _run_record(run_id: str, session_id: str, final_truth_id: str, success: bool) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_state": "completed" if success else "terminal_non_success",
        "current_attempt_id": f"{run_id}:attempt:0001",
        "current_attempt_state": "attempt_completed",
        "final_truth_record_id": final_truth_id,
        "policy_snapshot_id": f"trusted-repo-policy:{run_id}",
        "configuration_snapshot_id": f"trusted-repo-config:{run_id}",
        "session_id": session_id,
    }


def _step_record(run_id: str, accepted: bool) -> dict[str, Any]:
    return {"step_count": 1 if accepted else 0, "latest_step_id": f"{run_id}:step:write-config" if accepted else "", "latest_resources_touched": [CONFIG_ARTIFACT_PATH] if accepted else []}


def _approval_request(run_id: str) -> dict[str, Any]:
    return {"approval_id": f"trusted-repo-approval:{run_id}", "status": "RESOLVED", "request_type": "tool_approval", "gate_mode": "approval_required", "reason": APPROVAL_REASON, "control_plane_target_ref": run_id, "target_artifact_path": CONFIG_ARTIFACT_PATH}


def _operator_action(run_id: str, session_id: str, decision: str) -> dict[str, Any]:
    return {"result": decision, "affected_resource_refs": [run_id, f"session:{session_id}", RESOURCE_ID]}


def _checkpoint(run_id: str, accepted: bool) -> dict[str, Any]:
    return {"checkpoint_id": f"trusted-repo-checkpoint:{run_id}:attempt:0001", "acceptance_outcome": "checkpoint_accepted" if accepted else "checkpoint_rejected", "policy_digest": "sha256:trusted-repo-change-policy-v1", "acceptance_dependent_reservation_refs": [f"trusted-repo-reservation:{run_id}"], "acceptance_dependent_lease_refs": [f"trusted-repo-lease:{run_id}"]}


def _resource(run_id: str) -> dict[str, Any]:
    return {"resource_id": RESOURCE_ID, "namespace_scope": CONFIG_ARTIFACT_PATH, "current_observed_state": f"lease_released:{RESOURCE_ID}:{CONFIG_ARTIFACT_PATH}", "provenance_ref": f"trusted-repo-lease:{run_id}"}


def _reservation(run_id: str, session_id: str) -> dict[str, Any]:
    return {"reservation_id": f"trusted-repo-reservation:{run_id}", "reservation_kind": "fixture_repo_path_reservation", "status": "reservation_released", "holder_ref": run_id, "target_scope_ref": f"session={session_id};path={CONFIG_ARTIFACT_PATH}"}


def _effect_journal(run_id: str, accepted: bool, validator: dict[str, Any]) -> dict[str, Any]:
    return {"effect_entry_count": 1 if accepted else 0, "latest_step_id": f"{run_id}:step:write-config" if accepted else "", "latest_authorization_basis_ref": f"trusted-repo-approval:{run_id}" if accepted else "", "latest_intended_target_ref": CONFIG_ARTIFACT_PATH if accepted else "", "latest_observed_result_ref": str(validator.get("artifact_digest") or ""), "latest_uncertainty_classification": "no_residual_uncertainty" if accepted else "not_executed"}


def _final_truth(final_truth_id: str, workflow_result: str) -> dict[str, Any]:
    return {"final_truth_record_id": final_truth_id, "result_class": workflow_result, "evidence_sufficiency_classification": "evidence_sufficient" if workflow_result == "success" else "evidence_blocks_success"}


def _forbidden_mutations(workspace: Path) -> list[str]:
    repo = workspace / "repo"
    if not repo.exists():
        return []
    allowed = (workspace / CONFIG_ARTIFACT_PATH).resolve()
    return [relative_to_repo(path) for path in repo.rglob("*") if path.is_file() and path.resolve() != allowed]


def _ensure_target_in_workspace(target: Path, workspace: Path) -> None:
    if not target.resolve().is_relative_to(workspace.resolve()):
        raise ValueError("trusted_repo_change_target_outside_workspace")


def _persist(path: Path, payload: dict[str, Any]) -> str:
    write_payload_with_diff_ledger(path, payload)
    return relative_to_repo(path)


def _file_digest(path: Path) -> str:
    return _sha256(path) if path.exists() else ""


def _sha256(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _without_time(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("recorded_at_utc", None)
    return result
