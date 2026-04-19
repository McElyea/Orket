from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.terraform_plan_review_fixture_support import run_fixture_case
from scripts.proof.trusted_terraform_plan_decision_bundle_support import (
    build_audit_publication_payload,
    build_authority_lineage,
    build_execution_context,
    build_flow_request,
    build_witness_bundle,
    forbidden_mutations,
    persist_payload,
    workspace_files,
)
from scripts.proof.trusted_terraform_plan_decision_contract import (
    AUDIT_PUBLICATION_FILENAME,
    DEFAULT_BUNDLE_NAME,
    DEFAULT_SCENARIO,
    DEFAULT_VALIDATOR_OUTPUT,
    DEFAULT_WORKSPACE_ROOT,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
    artifact_ref,
    now_utc_iso,
    review_artifact_relative_path,
    validate_terraform_plan_decision_run,
)
from scripts.proof.trusted_terraform_plan_decision_verifier import verify_trusted_terraform_plan_decision_bundle_payload

LIVE_RUN_SCHEMA_VERSION = "trusted_terraform_plan_decision_live_run.v1"
SCENARIOS = {"risky_publish", "degraded_publish", "no_publish_invalid_json", "blocked_capability"}


def execute_trusted_terraform_plan_decision(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    scenario: str = DEFAULT_SCENARIO,
    run_index: int = 1,
) -> dict[str, Any]:
    settings = _scenario_settings(scenario)
    context = build_execution_context(workspace_root=workspace_root, scenario=scenario, run_index=run_index)
    before_files = workspace_files(context["workspace"])
    result, case, _s3, _model, publisher = asyncio.run(
        run_fixture_case(
            workspace=context["service_workspace"],
            case_name=str(settings["case_name"]),
            model_error=settings.get("model_error"),
            prohibited_capability_attempt=str(settings.get("prohibited_capability_attempt") or ""),
        )
    )
    after_files = workspace_files(context["workspace"])
    execution_trace_ref = str(result.governance_artifact.execution_trace_ref)
    expected_review_path = review_artifact_relative_path(context["session_id"], execution_trace_ref)
    review_artifact_path = Path(result.artifact_bundle.artifact_paths["final_review"])
    audit_publication = build_audit_publication_payload(run_id=context["run_id"], publisher=publisher)
    flow_request = build_flow_request(
        run_id=context["run_id"],
        session_id=context["session_id"],
        case_name=case.name,
        execution_trace_ref=execution_trace_ref,
        plan_s3_uri=case.plan_s3_uri,
        forbidden_operations=case.forbidden_operations,
    )
    flow_ref = persist_payload(context["run_root"] / "trusted_terraform_plan_decision_flow.json", flow_request)
    audit_ref = persist_payload(context["run_root"] / AUDIT_PUBLICATION_FILENAME, audit_publication) if audit_publication else ""
    validator_input = {
        "input_artifact": result.input_artifact.to_dict(),
        "deterministic_analysis": result.deterministic_analysis.to_dict(),
        "model_summary": result.model_summary.to_dict(),
        "final_review": result.final_review.to_dict(),
        "governance_artifact": result.governance_artifact.to_dict(),
        "audit_publication": audit_publication,
        "review_artifact_ref": artifact_ref("final_review", review_artifact_path, context["workspace"], ref_path=expected_review_path),
        "expected_review_artifact_path": expected_review_path,
        "forbidden_mutations": forbidden_mutations(before_files, after_files, context["run_root"], context["service_workspace"]),
    }
    validator = validate_terraform_plan_decision_run(validator_input)
    validator_ref = persist_payload(context["run_root"] / "trusted_terraform_plan_decision_validator.json", validator)
    write_payload_with_diff_ledger(DEFAULT_VALIDATOR_OUTPUT, validator)
    authority = build_authority_lineage(
        run_id=context["run_id"],
        session_id=context["session_id"],
        flow_request=flow_request,
        result=result.to_dict(),
        validator=validator,
        audit_publication=audit_publication,
        expected_review_path=expected_review_path,
    )
    authority_ref = persist_payload(context["run_root"] / "trusted_terraform_plan_decision_run_authority.json", authority)
    bundle = build_witness_bundle(
        context=context,
        result=result.to_dict(),
        flow_ref=flow_ref,
        authority=authority,
        authority_ref=authority_ref,
        validator=validator,
        validator_ref=validator_ref,
        expected_review_path=expected_review_path,
        audit_publication=audit_publication,
        audit_ref=audit_ref,
        forbidden_mutations=validator_input["forbidden_mutations"],
    )
    bundle_ref = persist_payload(context["run_root"] / DEFAULT_BUNDLE_NAME, bundle)
    report = verify_trusted_terraform_plan_decision_bundle_payload(bundle, evidence_ref=bundle_ref)
    return _live_payload(
        context=context,
        case_name=case.name,
        plan_s3_uri=case.plan_s3_uri,
        scenario=scenario,
        expected=settings,
        workflow_result=result.to_dict(),
        flow_ref=flow_ref,
        authority_ref=authority_ref,
        validator_ref=validator_ref,
        bundle_ref=bundle_ref,
        validator=validator,
        report=report,
        bundle=bundle,
    )


def persist_live_run(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return write_payload_with_diff_ledger(path.resolve(), payload)


def _scenario_settings(scenario: str) -> dict[str, Any]:
    table = {
        "risky_publish": {"case_name": "explicit_destroy", "expected_execution_status": "success", "expected_publish_decision": "normal_publish", "expected_report_result": "success"},
        "degraded_publish": {"case_name": "explicit_destroy", "model_error": RuntimeError("bedrock_down"), "expected_execution_status": "degraded", "expected_publish_decision": "degraded_publish", "expected_report_result": "success"},
        "no_publish_invalid_json": {"case_name": "invalid_json_plan", "expected_execution_status": "failure", "expected_publish_decision": "no_publish", "expected_report_result": "failure"},
        "blocked_capability": {"case_name": "create_update_only", "prohibited_capability_attempt": "shell_execution", "expected_execution_status": "blocked_by_policy", "expected_publish_decision": "no_publish", "expected_report_result": "failure"},
    }
    if scenario not in table:
        raise ValueError(f"unsupported_trusted_terraform_plan_decision_scenario:{scenario}")
    return dict(table[scenario])


def _live_payload(
    *,
    context: dict[str, Any],
    case_name: str,
    plan_s3_uri: str,
    scenario: str,
    expected: dict[str, Any],
    workflow_result: dict[str, Any],
    flow_ref: str,
    authority_ref: str,
    validator_ref: str,
    bundle_ref: str,
    validator: dict[str, Any],
    report: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    governance = workflow_result["governance_artifact"]
    proof_ok = (
        governance["execution_status"] == expected["expected_execution_status"]
        and governance["publish_decision"] == expected["expected_publish_decision"]
        and report.get("observed_result") == expected["expected_report_result"]
    )
    return {
        "schema_version": LIVE_RUN_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live",
        "scenario": scenario,
        "observed_path": "primary" if proof_ok else "blocked",
        "observed_result": "success" if proof_ok else "failure",
        "workflow_result": governance["observed_result_classification"],
        "execution_status": governance["execution_status"],
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "run_id": context["run_id"],
        "session_id": context["session_id"],
        "case_name": case_name,
        "plan_s3_uri": plan_s3_uri,
        "publish_decision": governance["publish_decision"],
        "risk_verdict": workflow_result["final_review"]["risk_verdict"],
        "summary_status": workflow_result["final_review"]["summary_status"],
        "flow_request_ref": flow_ref,
        "run_authority_ref": authority_ref,
        "validator_ref": validator_ref,
        "witness_bundle_ref": bundle_ref,
        "validator_result": validator,
        "witness_report": report,
        "bundle_id": str(bundle.get("bundle_id") or ""),
    }
