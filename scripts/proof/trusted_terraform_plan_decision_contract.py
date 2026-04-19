from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from scripts.proof.trusted_run_witness_contract import (
    BUNDLE_SCHEMA_VERSION,
    DEFAULT_BUNDLE_NAME,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    PROOF_RESULTS_ROOT,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    now_utc_iso,
    relative_to_repo,
    stable_json_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TRUSTED_TERRAFORM_COMPARE_SCOPE = "trusted_terraform_plan_decision_v1"
CONTRACT_VERDICT_SCHEMA_VERSION = "trusted_terraform_plan_decision_contract_verdict.v1"
VALIDATOR_SCHEMA_VERSION = "trusted_terraform_plan_decision_validator.v1"
WORKFLOW_REQUEST_SCHEMA_VERSION = "trusted_terraform_plan_decision.flow_request.v1"
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "workspace" / "trusted_terraform_plan_decision"
DEFAULT_LIVE_RUN_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_live_run.json"
DEFAULT_VALIDATOR_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_validator.json"
DEFAULT_CAMPAIGN_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_witness_verification.json"
DEFAULT_OFFLINE_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_offline_verifier.json"
REVIEW_ARTIFACT_FILENAME = "final_review.json"
AUDIT_PUBLICATION_FILENAME = "trusted_terraform_plan_decision_audit_publication.json"
DEFAULT_SCENARIO = "risky_publish"
MUST_CATCH_OUTCOMES = [
    "invalid_json_plan_input",
    "forbidden_operation_hits_drift",
    "risk_verdict_drift",
    "publish_without_complete_analysis",
    "audit_publication_without_publish",
    "undeclared_durable_mutation",
    "compare_scope_missing_or_unsupported",
    "operator_surface_missing",
    "missing_final_truth",
]


def runtime_root_relative_path(session_id: str) -> str:
    return f"runtime/{session_id}"


def review_artifact_relative_path(session_id: str, execution_trace_ref: str) -> str:
    safe_trace = execution_trace_ref.replace("\\", "-").replace("/", "-").strip() or "terraform-plan-review"
    return f"{runtime_root_relative_path(session_id)}/terraform_plan_reviews/{safe_trace}/{REVIEW_ARTIFACT_FILENAME}"


def audit_publication_relative_path(session_id: str) -> str:
    return f"runs/{session_id}/{AUDIT_PUBLICATION_FILENAME}"


def artifact_ref(kind: str, path: Path, workspace_root: Path, *, ref_path: str | None = None) -> dict[str, Any]:
    exists = path.exists()
    return {
        "kind": kind,
        "path": ref_path or _relative_to_workspace(path, workspace_root) if exists else "",
        "digest": _file_sha256(path) if exists else "",
        "exists": exists,
    }


def validate_terraform_plan_decision_run(run_payload: dict[str, Any]) -> dict[str, Any]:
    input_artifact = _as_dict(run_payload.get("input_artifact"))
    deterministic = _as_dict(run_payload.get("deterministic_analysis"))
    model_summary = _as_dict(run_payload.get("model_summary"))
    final_review = _as_dict(run_payload.get("final_review"))
    governance = _as_dict(run_payload.get("governance_artifact"))
    audit_publication = _as_dict(run_payload.get("audit_publication"))
    review_artifact_ref = _as_dict(run_payload.get("review_artifact_ref"))
    expected_review_path = _text(run_payload.get("expected_review_artifact_path"))
    actual_review_path = _text(review_artifact_ref.get("path"))
    forbidden_mutations = [str(item) for item in run_payload.get("forbidden_mutations") or [] if str(item).strip()]
    failures: list[str] = []
    passed: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    def check(check_id: str, passed_ok: bool, reason: str) -> None:
        target = passed if passed_ok else failed
        target.append({"id": check_id, "status": "pass" if passed_ok else "fail", **({} if passed_ok else {"reason": reason})})
        if not passed_ok:
            _append_unique(failures, reason)

    warnings = [str(item) for item in deterministic.get("warnings") or []]
    json_valid = "invalid_json_plan" not in warnings and "invalid_json_root" not in warnings
    deterministic_complete = deterministic.get("analysis_complete") is True
    deterministic_hits = [_normalize_forbidden_hit(item) for item in deterministic.get("forbidden_operation_hits") or []]
    final_hits = [_normalize_forbidden_hit(item) for item in final_review.get("forbidden_operation_hits") or []]
    expected_verdict = "risky_for_v1_policy" if deterministic_hits else "safe_for_v1_policy"
    publish_decision = _text(governance.get("publish_decision"))
    publish_allowed = deterministic_complete or publish_decision == "no_publish"
    audit_present = bool(audit_publication)
    audit_matches = _audit_matches_final_review(audit_publication, final_review)

    check("plan_input_valid_json", json_valid, "invalid_json_plan_input")
    check("deterministic_analysis_complete", deterministic_complete, "publish_without_complete_analysis")
    check("review_artifact_path", actual_review_path == expected_review_path and bool(_text(review_artifact_ref.get("digest"))), "risk_verdict_drift")
    check("plan_hash_preserved", _text(input_artifact.get("plan_hash")) and _text(input_artifact.get("plan_hash")) == _text(final_review.get("plan_hash")), "risk_verdict_drift")
    check("forbidden_hits_preserved", deterministic_hits == final_hits, "forbidden_operation_hits_drift")
    check("risk_verdict_matches_deterministic_rule", _text(final_review.get("risk_verdict")) == expected_verdict, "risk_verdict_drift")
    check("publish_decision_requires_complete_analysis", publish_allowed, "publish_without_complete_analysis")
    check(
        "summary_cannot_override_verdict",
        _text(final_review.get("risk_verdict")) == expected_verdict and _text(model_summary.get("summary_status")) == _text(final_review.get("summary_status")),
        "risk_verdict_drift",
    )
    check(
        "audit_publication_alignment",
        (publish_decision == "no_publish" and not audit_present) or (publish_decision != "no_publish" and audit_present and audit_matches),
        "audit_publication_without_publish",
    )
    check("forbidden_mutation_boundary", not forbidden_mutations, "undeclared_durable_mutation")

    report = {
        "schema_version": VALIDATOR_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "expected_review_artifact_path": expected_review_path,
        "review_artifact_digest": _text(review_artifact_ref.get("digest")),
        "deterministic_analysis_digest": stable_json_digest(deterministic),
        "governance_artifact_digest": stable_json_digest(governance),
        "audit_publication_digest": stable_json_digest(_as_dict(audit_publication.get("item"))) if audit_present else "",
        "validation_result": "pass" if not failures else "fail",
        "passed_checks": passed,
        "failed_checks": failed,
        "missing_evidence": _unique(failures),
    }
    report["validator_signature_digest"] = stable_json_digest(_validator_signature_material(report))
    return report


def build_contract_verdict(bundle: dict[str, Any]) -> dict[str, Any]:
    clean = _without_diff_ledger(bundle)
    authority = _as_dict(clean.get("authority_lineage"))
    observed = _as_dict(clean.get("observed_effect"))
    validator = _as_dict(clean.get("validator_result"))
    review_artifact = _artifact_ref_by_kind(clean, "final_review")
    run_id = _text(clean.get("run_id"))
    session_id = _text(clean.get("session_id"))
    failures: list[str] = []
    checks: list[dict[str, str]] = []

    def check(check_id: str, passed: bool, failure: str) -> None:
        checks.append({"id": check_id, "status": "pass" if passed else "fail"})
        if not passed:
            _append_unique(failures, failure)

    check("schema", clean.get("schema_version") == BUNDLE_SCHEMA_VERSION, "schema_version_missing_or_unsupported")
    check("compare_scope", clean.get("compare_scope") == TRUSTED_TERRAFORM_COMPARE_SCOPE, "compare_scope_missing_or_unsupported")
    check("operator_surface", clean.get("operator_surface") == OPERATOR_SURFACE, "operator_surface_missing")
    check("claim_tier", clean.get("claim_tier") == FALLBACK_CLAIM_TIER, "single_bundle_claim_tier_must_be_lab_only")
    check("policy_configuration", _has_policy_configuration(clean), "policy_or_configuration_missing")
    check("governed_input", _governed_input_ok(authority), "governed_input_missing")
    check("review_artifact_path", observed.get("actual_output_artifact_path") == _text(review_artifact.get("path")), "risk_verdict_drift")
    check("review_artifact_digest", _text(review_artifact.get("digest")) == _text(observed.get("artifact_digest")), "risk_verdict_drift")
    check("validator_present", validator.get("schema_version") == VALIDATOR_SCHEMA_VERSION, "missing_validator_result")
    check("validator_passed", validator.get("validation_result") == "pass", "validator_failed")
    _append_validator_failures(failures, validator)
    check("audit_publication", _audit_authority_ok(authority, observed), "audit_publication_without_publish")
    check("forbidden_mutations", not observed.get("forbidden_mutations"), "undeclared_durable_mutation")
    check("effect_journal", _effect_journal_ok(authority), "missing_effect_evidence")
    check("final_truth", _final_truth_ok(authority, run_id), "missing_final_truth")
    check("run_id_lineage", _run_id_lineage_ok(authority, run_id, session_id), "canonical_run_id_drift")

    return {
        "schema_version": CONTRACT_VERDICT_SCHEMA_VERSION,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "verdict": "pass" if not failures else "fail",
        "checks": checks,
        "failures": _unique(failures),
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
        "verdict_signature_digest": stable_json_digest(_verdict_signature_material(checks)),
    }


def _validator_signature_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": VALIDATOR_SCHEMA_VERSION,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "review_artifact_digest": report.get("review_artifact_digest"),
        "deterministic_analysis_digest": report.get("deterministic_analysis_digest"),
        "governance_artifact_digest": report.get("governance_artifact_digest"),
        "audit_publication_digest": report.get("audit_publication_digest"),
        "validation_result": report.get("validation_result"),
        "checks": {item["id"]: item["status"] for item in list(report.get("passed_checks") or []) + list(report.get("failed_checks") or [])},
        "missing_evidence": list(report.get("missing_evidence") or []),
    }


def _verdict_signature_material(checks: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_VERDICT_SCHEMA_VERSION,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "checks": {item["id"]: item["status"] for item in checks},
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
    }


def _has_policy_configuration(bundle: dict[str, Any]) -> bool:
    keys = ("policy_digest", "policy_snapshot_ref", "configuration_snapshot_ref", "control_bundle_ref")
    return all(bool(_text(bundle.get(key))) for key in keys)


def _governed_input_ok(authority: dict[str, Any]) -> bool:
    governed_input = _as_dict(authority.get("governed_input"))
    return (
        governed_input.get("schema_version") == WORKFLOW_REQUEST_SCHEMA_VERSION
        and bool(_text(governed_input.get("plan_s3_uri")))
        and isinstance(governed_input.get("forbidden_operations"), list)
    )


def _audit_authority_ok(authority: dict[str, Any], observed: dict[str, Any]) -> bool:
    publish_decision = _text(observed.get("publish_decision"))
    audit = _as_dict(authority.get("audit_publication"))
    return (publish_decision == "no_publish" and not audit) or (
        publish_decision != "no_publish"
        and bool(_text(audit.get("publication_id")))
        and bool(_text(audit.get("audit_item_digest")))
    )


def _effect_journal_ok(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    return int(journal.get("effect_entry_count") or 0) >= 1 and _text(journal.get("latest_observed_result_ref"))


def _final_truth_ok(authority: dict[str, Any], run_id: str) -> bool:
    final_truth = _as_dict(authority.get("final_truth"))
    return run_id in _text(final_truth.get("final_truth_record_id")) and final_truth.get("result_class") == "success"


def _run_id_lineage_ok(authority: dict[str, Any], run_id: str, session_id: str) -> bool:
    run = _as_dict(authority.get("run"))
    final_truth = _as_dict(authority.get("final_truth"))
    step = _as_dict(authority.get("step"))
    return (
        bool(run_id)
        and bool(session_id)
        and session_id in run_id
        and run.get("run_id") == run_id
        and run.get("final_truth_record_id") == final_truth.get("final_truth_record_id")
        and run_id in _text(step.get("latest_step_id"))
    )


def _artifact_ref_by_kind(bundle: dict[str, Any], kind: str) -> dict[str, Any]:
    for ref in bundle.get("artifact_refs") or []:
        if isinstance(ref, dict) and ref.get("kind") == kind:
            return ref
    return {}


def _audit_matches_final_review(audit_publication: dict[str, Any], final_review: dict[str, Any]) -> bool:
    item = _as_dict(audit_publication.get("item"))
    return bool(item) and all(
        _text(item.get(key)) == _text(final_review.get(key))
        for key in ("plan_hash", "plan_s3_uri", "risk_verdict", "summary_status", "policy_bundle_id", "execution_trace_ref", "created_at")
    )


def _normalize_forbidden_hit(value: Any) -> dict[str, str]:
    item = _as_dict(value)
    return {
        "operation": _text(item.get("operation")),
        "address": _text(item.get("address")),
        "provider_name": _text(item.get("provider_name")),
        "resource_type": _text(item.get("resource_type")),
    }


def _append_validator_failures(failures: list[str], validator: dict[str, Any]) -> None:
    for item in validator.get("missing_evidence") or []:
        _append_unique(failures, str(item))


def _relative_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return relative_to_repo(path)


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _without_diff_ledger(value: Any) -> dict[str, Any]:
    copied = copy.deepcopy(value)
    if isinstance(copied, dict):
        copied.pop("diff_ledger", None)
        return copied
    return {}


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append_unique(result, value)
    return result
