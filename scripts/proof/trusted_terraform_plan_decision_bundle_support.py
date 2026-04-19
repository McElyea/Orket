from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.trusted_terraform_plan_decision_contract import (
    AUDIT_PUBLICATION_FILENAME,
    DEFAULT_BUNDLE_NAME,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
    WORKFLOW_REQUEST_SCHEMA_VERSION,
    artifact_ref,
    audit_publication_relative_path,
    build_contract_verdict,
    now_utc_iso,
    relative_to_repo,
    review_artifact_relative_path,
    stable_json_digest,
)


def build_execution_context(*, workspace_root: Path, scenario: str, run_index: int) -> dict[str, Any]:
    workspace = workspace_root.resolve()
    session_id = f"trusted-terraform-plan-decision-{scenario}-{run_index:02d}"
    run_id = f"trusted-terraform-run:{session_id}:0001"
    run_root = workspace / "runs" / session_id
    service_workspace = workspace / "runtime" / session_id
    run_root.mkdir(parents=True, exist_ok=True)
    service_workspace.mkdir(parents=True, exist_ok=True)
    return {
        "workspace": workspace,
        "run_root": run_root,
        "service_workspace": service_workspace,
        "session_id": session_id,
        "run_id": run_id,
    }


def build_flow_request(
    *,
    run_id: str,
    session_id: str,
    case_name: str,
    execution_trace_ref: str,
    plan_s3_uri: str,
    forbidden_operations: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": WORKFLOW_REQUEST_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "request_id": f"trusted-terraform-plan-decision-request:{session_id}",
        "run_id": run_id,
        "session_id": session_id,
        "case_name": case_name,
        "plan_s3_uri": plan_s3_uri,
        "forbidden_operations": list(forbidden_operations),
        "policy_bundle_id": "terraform_plan_reviewer_v1",
        "execution_trace_ref": execution_trace_ref,
        "task": "Witness one bounded Terraform plan review decision under the governed-proof wrapper.",
    }


def build_audit_publication_payload(*, run_id: str, publisher: Any) -> dict[str, Any]:
    if not publisher.calls:
        return {}
    table_name, item = publisher.calls[0]
    return {
        "publication_id": f"trusted-terraform-audit:{run_id}",
        "table_name": table_name,
        "item": dict(item),
        "audit_item_digest": stable_json_digest(item),
    }


def build_authority_lineage(
    *,
    run_id: str,
    session_id: str,
    flow_request: dict[str, Any],
    result: dict[str, Any],
    validator: dict[str, Any],
    audit_publication: dict[str, Any],
    expected_review_path: str,
) -> dict[str, Any]:
    governance = result["governance_artifact"]
    final_truth_id = f"trusted-terraform-final-truth:{run_id}"
    success = governance["publish_decision"] != "no_publish"
    return {
        "governed_input": _without_time(flow_request),
        "run": _run_record(run_id, session_id, final_truth_id, success),
        "step": _step_record(run_id, governance["publish_decision"], expected_review_path),
        "review_decision": {
            "risk_verdict": result["final_review"]["risk_verdict"],
            "publish_decision": governance["publish_decision"],
            "summary_status": result["final_review"]["summary_status"],
            "final_verdict_source": governance["final_verdict_source"],
        },
        "audit_publication": audit_publication,
        "effect_journal": _effect_journal(run_id, expected_review_path, validator, audit_publication),
        "final_truth": _final_truth(final_truth_id, success),
    }


def build_witness_bundle(
    *,
    context: dict[str, Any],
    result: dict[str, Any],
    flow_ref: str,
    authority: dict[str, Any],
    authority_ref: str,
    validator: dict[str, Any],
    validator_ref: str,
    expected_review_path: str,
    audit_publication: dict[str, Any],
    audit_ref: str,
    forbidden_mutations: list[str],
) -> dict[str, Any]:
    control_bundle = {
        "policy_digest": _policy_digest(result),
        "configuration_snapshot_ref": f"trusted-terraform-config:{context['run_id']}",
        "validator_signature_digest": validator.get("validator_signature_digest"),
    }
    artifact_refs = _artifact_refs(
        workspace=context["workspace"],
        run_root=context["run_root"],
        session_id=context["session_id"],
        result=result,
        audit_publication=audit_publication,
    )
    bundle = {
        "schema_version": "trusted_run.witness_bundle.v1",
        "bundle_id": f"trusted-terraform-bundle:{context['run_id']}",
        "recorded_at_utc": now_utc_iso(),
        "run_id": context["run_id"],
        "session_id": context["session_id"],
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "claim_tier": FALLBACK_CLAIM_TIER,
        "policy_digest": control_bundle["policy_digest"],
        "policy_snapshot_ref": f"trusted-terraform-policy:{context['run_id']}",
        "configuration_snapshot_ref": control_bundle["configuration_snapshot_ref"],
        "control_bundle_ref": authority_ref,
        "control_bundle_digest": stable_json_digest(control_bundle),
        "resolution_basis": {"flow_request_ref": flow_ref, "run_authority_ref": authority_ref, "validator_ref": validator_ref, "audit_publication_ref": audit_ref},
        "trusted_terraform_plan_decision_slice": {
            "plan_s3_uri": result["input_artifact"]["plan_s3_uri"],
            "execution_trace_ref": result["governance_artifact"]["execution_trace_ref"],
            "policy_bundle_id": result["governance_artifact"]["policy_bundle_id"],
        },
        "artifact_refs": artifact_refs,
        "authority_lineage": authority,
        "validator_result": validator,
        "observed_effect": {
            "expected_output_artifact_path": expected_review_path,
            "actual_output_artifact_path": expected_review_path if artifact_path(result, "final_review").exists() else "",
            "output_exists": artifact_path(result, "final_review").exists(),
            "artifact_digest": artifact_refs[5]["digest"],
            "risk_verdict": result["final_review"]["risk_verdict"],
            "publish_decision": result["governance_artifact"]["publish_decision"],
            "summary_status": result["final_review"]["summary_status"],
            "final_verdict_source": result["governance_artifact"]["final_verdict_source"],
            "deterministic_analysis_complete": result["deterministic_analysis"]["analysis_complete"],
            "audit_publication_present": bool(audit_publication),
            "forbidden_mutations": list(forbidden_mutations),
        },
    }
    bundle["contract_verdict"] = build_contract_verdict(bundle)
    return bundle


def artifact_path(result: dict[str, Any], kind: str) -> Path:
    return Path(result["artifact_bundle"]["artifact_paths"][kind])


def workspace_files(root: Path) -> set[Path]:
    return {path.resolve() for path in root.rglob("*") if path.is_file()}


def forbidden_mutations(before: set[Path], after: set[Path], run_root: Path, service_workspace: Path) -> list[str]:
    created = [path for path in sorted(after - before) if not path.is_relative_to(run_root.resolve()) and not path.is_relative_to(service_workspace.resolve())]
    return [relative_to_repo(path) for path in created]


def persist_payload(path: Path, payload: dict[str, Any]) -> str:
    write_payload_with_diff_ledger(path, payload)
    return relative_to_repo(path)


def _artifact_refs(*, workspace: Path, run_root: Path, session_id: str, result: dict[str, Any], audit_publication: dict[str, Any]) -> list[dict[str, Any]]:
    refs = [
        artifact_ref("run_authority", run_root / "trusted_terraform_plan_decision_run_authority.json", workspace),
        artifact_ref("validator_report", run_root / "trusted_terraform_plan_decision_validator.json", workspace),
        artifact_ref("input_artifact", artifact_path(result, "input_artifact"), workspace),
        artifact_ref("deterministic_analysis", artifact_path(result, "deterministic_analysis"), workspace),
        artifact_ref("model_summary", artifact_path(result, "model_summary"), workspace),
        artifact_ref("final_review", artifact_path(result, "final_review"), workspace, ref_path=review_artifact_relative_path(session_id, result["governance_artifact"]["execution_trace_ref"])),
        artifact_ref("governance_artifact", artifact_path(result, "governance_artifact"), workspace),
        artifact_ref("artifact_manifest", artifact_path(result, "manifest"), workspace),
    ]
    if audit_publication:
        refs.append(artifact_ref("audit_publication", run_root / AUDIT_PUBLICATION_FILENAME, workspace, ref_path=audit_publication_relative_path(session_id)))
    return refs


def _run_record(run_id: str, session_id: str, final_truth_id: str, success: bool) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_state": "completed" if success else "terminal_non_success",
        "current_attempt_id": f"{run_id}:attempt:0001",
        "current_attempt_state": "attempt_completed",
        "final_truth_record_id": final_truth_id,
        "policy_snapshot_id": f"trusted-terraform-policy:{run_id}",
        "configuration_snapshot_id": f"trusted-terraform-config:{run_id}",
        "session_id": session_id,
    }


def _step_record(run_id: str, publish_decision: str, expected_review_path: str) -> dict[str, Any]:
    return {
        "step_count": 1,
        "latest_step_id": f"{run_id}:step:publish-review",
        "latest_resources_touched": [expected_review_path] if publish_decision != "no_publish" else [],
    }


def _effect_journal(run_id: str, expected_review_path: str, validator: dict[str, Any], audit_publication: dict[str, Any]) -> dict[str, Any]:
    return {
        "effect_entry_count": 2 if audit_publication else 1,
        "latest_step_id": f"{run_id}:step:publish-review",
        "latest_authorization_basis_ref": f"trusted-terraform-policy:{run_id}",
        "latest_intended_target_ref": expected_review_path,
        "latest_observed_result_ref": str(validator.get("validator_signature_digest") or ""),
        "latest_uncertainty_classification": "no_residual_uncertainty",
    }


def _final_truth(final_truth_id: str, success: bool) -> dict[str, Any]:
    return {
        "final_truth_record_id": final_truth_id,
        "result_class": "success" if success else "failure",
        "evidence_sufficiency_classification": "evidence_sufficient" if success else "evidence_blocks_success",
    }


def _policy_digest(result: dict[str, Any]) -> str:
    return stable_json_digest(
        {
            "policy_bundle_id": result["governance_artifact"]["policy_bundle_id"],
            "execution_trace_ref": result["governance_artifact"]["execution_trace_ref"],
            "forbidden_operations": [item["operation"] for item in result["deterministic_analysis"]["forbidden_operation_hits"]],
        }
    )


def _without_time(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("recorded_at_utc", None)
    return result
