#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.terraform_plan_review_live_support import (
    LiveTerraformReviewConfig,
    bedrock_smoke_runtime_operation,
    is_environment_blocker,
    live_config_from_env,
    missing_required_env,
    run_live_review,
)
from scripts.proof.trusted_terraform_plan_decision_contract import (
    DEFAULT_BUNDLE_NAME,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    PROOF_RESULTS_ROOT,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
    now_utc_iso,
    relative_to_repo,
)
from scripts.proof.trusted_terraform_plan_decision_verifier import verify_trusted_terraform_plan_decision_bundle_payload
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

RUNTIME_SMOKE_SCHEMA_VERSION = "trusted_terraform_plan_decision_live_runtime.v1"
DEFAULT_RUNTIME_SMOKE_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_live_runtime.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    env = live_config_from_env()
    parser = argparse.ArgumentParser(description="Run the Trusted Terraform Plan Decision provider-backed runtime smoke path.")
    parser.add_argument("--workspace-root", default="workspace/trusted_terraform_plan_decision", help="Workspace root for the proof run.")
    parser.add_argument("--run-index", type=int, default=1, help="Stable run index used in generated proof ids.")
    parser.add_argument("--output", default=str(DEFAULT_RUNTIME_SMOKE_OUTPUT), help="Stable live runtime output path.")
    parser.add_argument("--plan-s3-uri", default=env.plan_s3_uri)
    parser.add_argument("--model-id", default=env.model_id)
    parser.add_argument("--region", default=env.region)
    parser.add_argument("--table-name", default=env.table_name)
    parser.add_argument("--created-at", default=env.created_at)
    parser.add_argument("--execution-trace-ref", default="trusted-terraform-plan-decision-live-runtime")
    parser.add_argument("--policy-bundle-id", default=env.policy_bundle_id)
    parser.add_argument("--expected-plan-hash", default=env.expected_plan_hash)
    parser.add_argument("--smoke-owner-marker", default=env.smoke_owner_marker)
    parser.add_argument("--json", action="store_true", help="Print the persisted live runtime proof JSON.")
    return parser.parse_args(argv)


def execute_trusted_terraform_plan_decision_runtime_smoke(
    *,
    workspace_root: Path,
    run_index: int,
    config: LiveTerraformReviewConfig,
) -> dict[str, Any]:
    context = build_execution_context(workspace_root=workspace_root, scenario="runtime-smoke", run_index=run_index)
    missing = missing_required_env(config)
    if missing:
        return _blocked_payload(context=context, config=config, reason=f"missing_required_env:{','.join(missing)}")
    before_files = workspace_files(context["workspace"])
    try:
        result, publisher = asyncio.run(run_live_review(workspace=context["service_workspace"], config=config))
    except ModuleNotFoundError:
        return _blocked_payload(context=context, config=config, reason="missing_dependency:boto3")
    except Exception as exc:  # noqa: BLE001 - CLI/proof boundary
        if is_environment_blocker(exc):
            return _blocked_payload(context=context, config=config, reason=str(exc))
        return _failure_payload(context=context, config=config, reason=str(exc))
    after_files = workspace_files(context["workspace"])
    workflow_result = result.to_dict()
    execution_trace_ref = str(result.governance_artifact.execution_trace_ref)
    flow_request = build_flow_request(
        run_id=context["run_id"],
        session_id=context["session_id"],
        case_name="provider_backed_runtime_smoke",
        execution_trace_ref=execution_trace_ref,
        plan_s3_uri=str(config.plan_s3_uri),
        forbidden_operations=list(config.forbidden_operations),
    )
    flow_ref = persist_payload(context["run_root"] / "trusted_terraform_plan_decision_flow.json", flow_request)
    audit_publication = build_audit_publication_payload(run_id=context["run_id"], publisher=publisher)
    audit_ref = persist_payload(context["run_root"] / "trusted_terraform_plan_decision_audit_publication.json", audit_publication) if audit_publication else ""
    validator_input = {
        "input_artifact": result.input_artifact.to_dict(),
        "deterministic_analysis": result.deterministic_analysis.to_dict(),
        "model_summary": result.model_summary.to_dict(),
        "final_review": result.final_review.to_dict(),
        "governance_artifact": result.governance_artifact.to_dict(),
        "audit_publication": audit_publication,
        "review_artifact_ref": _artifact_ref(
            result=result,
            workspace=context["workspace"],
            session_id=context["session_id"],
        ),
        "expected_review_artifact_path": _runtime_review_path(context["session_id"], execution_trace_ref),
        "forbidden_mutations": forbidden_mutations(before_files, after_files, context["run_root"], context["service_workspace"]),
    }
    from scripts.proof.trusted_terraform_plan_decision_contract import validate_terraform_plan_decision_run

    validator = validate_terraform_plan_decision_run(validator_input)
    validator_ref = persist_payload(context["run_root"] / "trusted_terraform_plan_decision_validator.json", validator)
    authority = build_authority_lineage(
        run_id=context["run_id"],
        session_id=context["session_id"],
        flow_request=flow_request,
        result=workflow_result,
        validator=validator,
        audit_publication=audit_publication,
        expected_review_path=_runtime_review_path(context["session_id"], execution_trace_ref),
    )
    authority_ref = persist_payload(context["run_root"] / "trusted_terraform_plan_decision_run_authority.json", authority)
    bundle = build_witness_bundle(
        context=context,
        result=workflow_result,
        flow_ref=flow_ref,
        authority=authority,
        authority_ref=authority_ref,
        validator=validator,
        validator_ref=validator_ref,
        expected_review_path=_runtime_review_path(context["session_id"], execution_trace_ref),
        audit_publication=audit_publication,
        audit_ref=audit_ref,
        forbidden_mutations=validator_input["forbidden_mutations"],
    )
    bundle_ref = persist_payload(context["run_root"] / DEFAULT_BUNDLE_NAME, bundle)
    report = verify_trusted_terraform_plan_decision_bundle_payload(bundle, evidence_ref=bundle_ref)
    return _success_payload(
        context=context,
        config=config,
        workflow_result=workflow_result,
        flow_ref=flow_ref,
        authority_ref=authority_ref,
        validator_ref=validator_ref,
        bundle_ref=bundle_ref,
        validator=validator,
        report=report,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    config = LiveTerraformReviewConfig(
        plan_s3_uri=str(args.plan_s3_uri),
        model_id=str(args.model_id),
        region=str(args.region),
        table_name=str(args.table_name),
        created_at=str(args.created_at),
        execution_trace_ref=str(args.execution_trace_ref),
        policy_bundle_id=str(args.policy_bundle_id),
        expected_plan_hash=str(args.expected_plan_hash),
        smoke_owner_marker=str(args.smoke_owner_marker),
    )
    payload = execute_trusted_terraform_plan_decision_runtime_smoke(
        workspace_root=Path(str(args.workspace_root)),
        run_index=int(args.run_index),
        config=config,
    )
    output = Path(str(args.output)).resolve()
    persisted = write_payload_with_diff_ledger(output, payload)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"execution_status={persisted.get('execution_status')}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") in {"success", "partial success"} else 1


def _runtime_review_path(session_id: str, execution_trace_ref: str) -> str:
    from scripts.proof.trusted_terraform_plan_decision_contract import review_artifact_relative_path

    return review_artifact_relative_path(session_id, execution_trace_ref)


def _artifact_ref(*, result: Any, workspace: Path, session_id: str) -> dict[str, Any]:
    from scripts.proof.trusted_terraform_plan_decision_contract import artifact_ref

    execution_trace_ref = str(result.governance_artifact.execution_trace_ref)
    review_path = Path(result.artifact_bundle.artifact_paths["final_review"])
    return artifact_ref(
        "final_review",
        review_path,
        workspace,
        ref_path=_runtime_review_path(session_id, execution_trace_ref),
    )


def _blocked_payload(*, context: dict[str, Any], config: LiveTerraformReviewConfig, reason: str) -> dict[str, Any]:
    return _base_payload(
        context=context,
        config=config,
        observed_path="blocked",
        observed_result="environment blocker",
        workflow_result="environment blocker",
        execution_status="environment_blocker",
        reason=reason,
    )


def _failure_payload(*, context: dict[str, Any], config: LiveTerraformReviewConfig, reason: str) -> dict[str, Any]:
    return _base_payload(
        context=context,
        config=config,
        observed_path="blocked",
        observed_result="failure",
        workflow_result="failure",
        execution_status="failure",
        reason=reason,
    )


def _base_payload(
    *,
    context: dict[str, Any],
    config: LiveTerraformReviewConfig,
    observed_path: str,
    observed_result: str,
    workflow_result: str,
    execution_status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": RUNTIME_SMOKE_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live",
        "runtime_mode": "provider_backed_smoke",
        "observed_path": observed_path,
        "observed_result": observed_result,
        "workflow_result": workflow_result,
        "execution_status": execution_status,
        "reason": reason,
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "run_id": context["run_id"],
        "session_id": context["session_id"],
        "plan_s3_uri": str(config.plan_s3_uri),
        "s3_input_ref": str(config.plan_s3_uri),
        "bedrock_model_id": str(config.model_id),
        "aws_region": str(config.region),
        "dynamodb_table": str(config.table_name),
        "plan_hash": str(config.expected_plan_hash or ""),
        "provider_interaction_summary": _provider_interaction_summary(
            config,
            attempted=_adapter_calls_from_failure_reason(reason),
        ),
        "blocker_taxonomy": _blocker_taxonomy(reason),
        "publish_decision": "no_publish",
        "risk_verdict": "",
        "summary_status": "summary_not_attempted",
        "flow_request_ref": "",
        "run_authority_ref": "",
        "validator_ref": "",
        "witness_bundle_ref": "",
        "validator_result": {},
        "witness_report": {},
    }


def _success_payload(
    *,
    context: dict[str, Any],
    config: LiveTerraformReviewConfig,
    workflow_result: dict[str, Any],
    flow_ref: str,
    authority_ref: str,
    validator_ref: str,
    bundle_ref: str,
    validator: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    governance = workflow_result["governance_artifact"]
    witness_ok = report.get("observed_result") == "success"
    return {
        "schema_version": RUNTIME_SMOKE_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live",
        "runtime_mode": "provider_backed_smoke",
        "observed_path": governance["observed_path_classification"] if witness_ok else "blocked",
        "observed_result": governance["observed_result_classification"] if witness_ok else "failure",
        "workflow_result": governance["observed_result_classification"],
        "execution_status": governance["execution_status"],
        "reason": "",
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "run_id": context["run_id"],
        "session_id": context["session_id"],
        "plan_s3_uri": str(config.plan_s3_uri),
        "s3_input_ref": str(config.plan_s3_uri),
        "bedrock_model_id": str(config.model_id),
        "aws_region": str(config.region),
        "dynamodb_table": str(config.table_name),
        "plan_hash": str(workflow_result["input_artifact"].get("plan_hash") or config.expected_plan_hash or ""),
        "provider_interaction_summary": _provider_interaction_summary(
            config,
            attempted=list(workflow_result["governance_artifact"].get("adapter_calls_attempted") or []),
        ),
        "blocker_taxonomy": "",
        "publish_decision": governance["publish_decision"],
        "risk_verdict": workflow_result["final_review"]["risk_verdict"],
        "summary_status": workflow_result["final_review"]["summary_status"],
        "flow_request_ref": flow_ref,
        "run_authority_ref": authority_ref,
        "validator_ref": validator_ref,
        "witness_bundle_ref": bundle_ref,
        "validator_result": validator,
        "witness_report": report,
    }


def _provider_interaction_summary(config: LiveTerraformReviewConfig, *, attempted: list[str]) -> list[dict[str, str]]:
    return [
        {
            "service": "s3",
            "operation": "GetObject",
            "resource_ref": str(config.plan_s3_uri),
            "status": "attempted" if "read_s3_object" in attempted else "not_attempted",
        },
        {
            "service": "bedrock-runtime",
            "operation": bedrock_smoke_runtime_operation(str(config.model_id)),
            "resource_ref": str(config.model_id),
            "status": "attempted" if "invoke_bedrock_model" in attempted else "not_attempted",
        },
        {
            "service": "dynamodb",
            "operation": "PutItem",
            "resource_ref": str(config.table_name),
            "status": "attempted" if "put_dynamodb_item" in attempted else "not_attempted",
        },
    ]


def _adapter_calls_from_failure_reason(reason: str) -> list[str]:
    text = str(reason or "")
    attempted: list[str] = []
    if "GetObject" in text or "NoSuchBucket" in text or "NoSuchKey" in text:
        attempted.append("read_s3_object")
    if "Converse" in text or "InvokeModel" in text or "bedrock" in text.lower():
        attempted.extend(["read_s3_object", "invoke_bedrock_model"])
    if "PutItem" in text or "dynamodb" in text.lower() or "ResourceNotFoundException" in text:
        attempted.extend(["read_s3_object", "invoke_bedrock_model", "put_dynamodb_item"])
    return sorted(set(attempted))


def _blocker_taxonomy(reason: str) -> str:
    text = str(reason or "")
    if text.startswith("missing_required_env"):
        return "missing_configuration"
    if "NoCredentials" in text or "credentials" in text or "UnrecognizedClient" in text:
        return "missing_credentials"
    if "AccessDenied" in text or "not authorized" in text:
        return "missing_permission"
    if "NoSuchKey" in text or "NoSuchBucket" in text or "404" in text:
        return "missing_object"
    if "unsupported_bedrock_model" in text:
        return "unsupported_model"
    if "ResourceNotFoundException" in text or "table" in text.lower():
        return "table_unavailable"
    return "runtime_failure" if text else ""


if __name__ == "__main__":
    raise SystemExit(main())
