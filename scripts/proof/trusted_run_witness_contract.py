from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.productflow.productflow_support import (
    PRODUCTFLOW_BUILDER_SEAT,
    PRODUCTFLOW_EPIC_ID,
    PRODUCTFLOW_ISSUE_ID,
    PRODUCTFLOW_OUTPUT_CONTENT,
    PRODUCTFLOW_OUTPUT_PATH,
    REPO_ROOT,
)

BUNDLE_SCHEMA_VERSION = "trusted_run.witness_bundle.v1"
REPORT_SCHEMA_VERSION = "trusted_run_witness_report.v1"
CONTRACT_VERDICT_SCHEMA_VERSION = "trusted_run_contract_verdict.v1"
COMPARE_SCOPE = "trusted_run_productflow_write_file_v1"
OPERATOR_SURFACE = "trusted_run_witness_report.v1"
TARGET_CLAIM_TIER = "verdict_deterministic"
FALLBACK_CLAIM_TIER = "non_deterministic_lab_only"
DEFAULT_BUNDLE_NAME = "trusted_run_witness_bundle.json"
PROOF_RESULTS_ROOT = REPO_ROOT / "benchmarks" / "results" / "proof"
DEFAULT_VERIFICATION_OUTPUT = PROOF_RESULTS_ROOT / "trusted_run_witness_verification.json"
APPROVAL_REASON = "approval_required_tool:write_file"
EXPECTED_ISSUE_STATUS = "done"
MUST_CATCH_OUTCOMES = [
    "missing_output_artifact",
    "wrong_output_content",
    "missing_approval_resolution",
    "missing_effect_evidence",
    "missing_final_truth",
    "canonical_run_id_drift",
]


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def stable_json_digest(payload: Any) -> str:
    canonical = json.dumps(_without_diff_ledger(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def relative_to_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def build_contract_verdict(bundle: dict[str, Any]) -> dict[str, Any]:
    clean_bundle = _without_diff_ledger(bundle)
    authority = _as_dict(clean_bundle.get("authority_lineage"))
    observed = _as_dict(clean_bundle.get("observed_effect"))
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, failure: str, detail: str = "") -> None:
        checks.append({"id": check_id, "status": "pass" if passed else "fail", "detail": detail})
        if not passed and failure not in failures:
            failures.append(failure)

    run_id = str(clean_bundle.get("run_id") or "").strip()
    session_id = str(clean_bundle.get("session_id") or "").strip()
    check("schema", clean_bundle.get("schema_version") == BUNDLE_SCHEMA_VERSION, "schema_version_missing_or_unsupported")
    check("compare_scope", clean_bundle.get("compare_scope") == COMPARE_SCOPE, "compare_scope_missing_or_unsupported")
    check("operator_surface", clean_bundle.get("operator_surface") == OPERATOR_SURFACE, "operator_surface_missing")
    check("claim_tier", bool(clean_bundle.get("claim_tier")), "claim_tier_missing")
    check("policy_configuration", _has_policy_configuration(clean_bundle), "policy_or_configuration_missing")
    check("artifact_refs", _has_required_artifact_refs(clean_bundle), "artifact_ref_missing")
    check("governed_input", _governed_input_ok(authority), "governed_input_missing")
    check("output_path", observed.get("actual_output_artifact_path") == PRODUCTFLOW_OUTPUT_PATH, "missing_output_artifact")
    check("output_content", observed.get("normalized_content") == PRODUCTFLOW_OUTPUT_CONTENT, "wrong_output_content")
    check("issue_status", observed.get("issue_status") == EXPECTED_ISSUE_STATUS, "wrong_terminal_issue_status")
    check("approval_request", _approval_request_ok(authority, run_id), "approval_request_missing_or_drifted")
    check("approval_resolution", _operator_action_ok(authority, run_id), "missing_approval_resolution")
    check("checkpoint", _checkpoint_ok(authority, run_id), "checkpoint_missing_or_drifted")
    check("resource_and_lease", _resource_and_lease_ok(authority), "resource_or_lease_evidence_missing")
    check("effect_journal", _effect_journal_ok(authority), "missing_effect_evidence")
    check("final_truth", _final_truth_ok(authority, run_id), "missing_final_truth")
    check("run_id_lineage", _run_id_lineage_ok(authority, run_id, session_id), "canonical_run_id_drift")

    signature_material = _verdict_signature_material(checks)
    return {
        "schema_version": CONTRACT_VERDICT_SCHEMA_VERSION,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "verdict": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
        "verdict_signature_digest": stable_json_digest(signature_material),
    }


def verify_witness_bundle_payload(bundle: dict[str, Any], *, evidence_ref: str = "") -> dict[str, Any]:
    from scripts.proof.control_plane_witness_substrate import evaluate_control_plane_witness_substrate
    from scripts.proof.trusted_run_invariant_model import evaluate_trusted_run_invariants

    clean_bundle = _without_diff_ledger(bundle)
    failures: list[str] = []
    included_verdict = clean_bundle.get("contract_verdict")
    if not isinstance(included_verdict, dict):
        failures.append("contract_verdict_missing")
        included_verdict = {}
    recomputed = build_contract_verdict(clean_bundle)
    invariant_model = evaluate_trusted_run_invariants(clean_bundle)
    substrate_model = evaluate_control_plane_witness_substrate(clean_bundle)
    included_digest = str(included_verdict.get("verdict_signature_digest") or "")
    recomputed_digest = str(recomputed.get("verdict_signature_digest") or "")
    if included_digest and included_digest != recomputed_digest:
        failures.append("contract_verdict_drift")
    if recomputed.get("verdict") != "pass":
        failures.extend(str(item) for item in recomputed.get("failures") or [])
    if invariant_model.get("result") != "pass":
        failures.extend(str(item) for item in invariant_model.get("failures") or [])
        failures.extend(str(item) for item in invariant_model.get("missing_proof_blockers") or [])
    if substrate_model.get("result") != "pass":
        failures.extend(str(item) for item in substrate_model.get("failures") or [])
        failures.extend(str(item) for item in substrate_model.get("missing_substrate_blockers") or [])
    failures = _unique(failures)
    success = not failures
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary" if clean_bundle.get("schema_version") == BUNDLE_SCHEMA_VERSION else "blocked",
        "observed_result": "success" if success else "failure",
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": str(clean_bundle.get("compare_scope") or ""),
        "operator_surface": OPERATOR_SURFACE,
        "bundle_id": str(clean_bundle.get("bundle_id") or ""),
        "run_id": str(clean_bundle.get("run_id") or ""),
        "session_id": str(clean_bundle.get("session_id") or ""),
        "policy_digest": str(clean_bundle.get("policy_digest") or ""),
        "control_bundle_ref": str(clean_bundle.get("control_bundle_ref") or ""),
        "evidence_ref": evidence_ref,
        "side_effect_free_verification": True,
        "contract_verdict": recomputed,
        "trusted_run_invariant_model": invariant_model,
        "control_plane_witness_substrate": substrate_model,
        "included_contract_verdict_digest": included_digest,
        "recomputed_contract_verdict_digest": recomputed_digest,
        "invariant_model_signature_digest": str(invariant_model.get("invariant_signature_digest") or ""),
        "substrate_signature_digest": str(substrate_model.get("substrate_signature_digest") or ""),
        "missing_evidence": failures,
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
    }


def build_campaign_verification_report(
    reports: list[dict[str, Any]],
    *,
    bundle_refs: list[str] | None = None,
    live_proof_refs: list[str] | None = None,
) -> dict[str, Any]:
    clean_reports = [_without_diff_ledger(report) for report in reports]
    success_reports = [report for report in clean_reports if report.get("observed_result") == "success"]
    digests = {
        str(_as_dict(report.get("contract_verdict")).get("verdict_signature_digest") or "")
        for report in success_reports
    }
    digests.discard("")
    invariant_digests = {
        str(
            report.get("invariant_model_signature_digest")
            or _as_dict(report.get("trusted_run_invariant_model")).get("invariant_signature_digest")
            or ""
        )
        for report in success_reports
    }
    invariant_digests.discard("")
    substrate_digests = {
        str(
            report.get("substrate_signature_digest")
            or _as_dict(report.get("control_plane_witness_substrate")).get("substrate_signature_digest")
            or ""
        )
        for report in success_reports
    }
    substrate_digests.discard("")
    must_catch_sets = {tuple(report.get("must_catch_outcomes") or []) for report in success_reports}
    side_effect_free = bool(success_reports) and all(
        report.get("side_effect_free_verification") is True for report in success_reports
    )
    stable = len(clean_reports) >= 2 and len(success_reports) == len(clean_reports) and len(digests) == 1
    stable = stable and len(invariant_digests) == 1 and len(substrate_digests) == 1
    stable = stable and len(must_catch_sets) == 1 and side_effect_free
    failures = _campaign_failures(
        clean_reports=clean_reports,
        stable=stable,
        digests=digests,
        invariant_digests=invariant_digests,
        substrate_digests=substrate_digests,
        side_effect_free=side_effect_free,
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live",
        "observed_path": "primary" if clean_reports else "blocked",
        "observed_result": "success" if stable else ("partial success" if success_reports else "failure"),
        "claim_tier": TARGET_CLAIM_TIER if stable else FALLBACK_CLAIM_TIER,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "run_count": len(clean_reports),
        "successful_verification_count": len(success_reports),
        "verdict_signature_digests": sorted(digests),
        "invariant_model_signature_digests": sorted(invariant_digests),
        "substrate_signature_digests": sorted(substrate_digests),
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
        "must_catch_outcomes_stable": len(must_catch_sets) == 1 if success_reports else False,
        "invariant_model_signature_stable": len(invariant_digests) == 1 if success_reports else False,
        "substrate_signature_stable": len(substrate_digests) == 1 if success_reports else False,
        "side_effect_free_verification": side_effect_free,
        "bundle_refs": list(bundle_refs or []),
        "live_proof_refs": list(live_proof_refs or []),
        "bundle_reports": clean_reports,
        "missing_evidence": failures,
    }


def blocked_report(*, run_index: int, reason: str, live_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live",
        "observed_path": "blocked",
        "observed_result": "failure",
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "run_index": run_index,
        "run_id": str(live_payload.get("run_id") or ""),
        "session_id": str(live_payload.get("session_id") or ""),
        "missing_evidence": [reason],
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
    }


def _has_policy_configuration(bundle: dict[str, Any]) -> bool:
    return all(
        bool(str(bundle.get(key) or "").strip())
        for key in ("policy_digest", "policy_snapshot_ref", "configuration_snapshot_ref", "control_bundle_ref")
    )


def _has_required_artifact_refs(bundle: dict[str, Any]) -> bool:
    refs = [ref for ref in bundle.get("artifact_refs") or [] if isinstance(ref, dict)]
    by_kind = {str(ref.get("kind") or ""): ref for ref in refs}
    return all(bool(by_kind.get(kind, {}).get("digest")) for kind in ("run_summary", "output_artifact"))


def _governed_input_ok(authority: dict[str, Any]) -> bool:
    governed_input = _as_dict(authority.get("governed_input"))
    return (
        governed_input.get("epic_id") == PRODUCTFLOW_EPIC_ID
        and governed_input.get("issue_id") == PRODUCTFLOW_ISSUE_ID
        and governed_input.get("seat") == PRODUCTFLOW_BUILDER_SEAT
    )


def _approval_request_ok(authority: dict[str, Any], run_id: str) -> bool:
    request = _as_dict(authority.get("approval_request"))
    return request.get("reason") == APPROVAL_REASON and request.get("control_plane_target_ref") == run_id


def _operator_action_ok(authority: dict[str, Any], run_id: str) -> bool:
    action = _as_dict(authority.get("operator_action"))
    affected_refs = [str(item) for item in action.get("affected_resource_refs") or []]
    return str(action.get("result") or "").lower() == "approved" and run_id in affected_refs


def _checkpoint_ok(authority: dict[str, Any], run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    checkpoint_id = str(checkpoint.get("checkpoint_id") or "")
    return run_id in checkpoint_id and checkpoint.get("acceptance_outcome") == "checkpoint_accepted"


def _resource_and_lease_ok(authority: dict[str, Any]) -> bool:
    resource = _as_dict(authority.get("resource"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    reservation_refs = checkpoint.get("acceptance_dependent_reservation_refs") or []
    lease_refs = checkpoint.get("acceptance_dependent_lease_refs") or []
    expected_resource = f"namespace:issue:{PRODUCTFLOW_ISSUE_ID}"
    return resource.get("resource_id") == expected_resource and bool(reservation_refs) and bool(lease_refs)


def _effect_journal_ok(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    return int(journal.get("effect_entry_count") or 0) >= 2 and journal.get("latest_uncertainty_classification") == "no_residual_uncertainty"


def _final_truth_ok(authority: dict[str, Any], run_id: str) -> bool:
    final_truth = _as_dict(authority.get("final_truth"))
    final_truth_id = str(final_truth.get("final_truth_record_id") or "")
    return (
        run_id in final_truth_id
        and final_truth.get("result_class") == "success"
        and final_truth.get("evidence_sufficiency_classification") == "evidence_sufficient"
    )


def _run_id_lineage_ok(authority: dict[str, Any], run_id: str, session_id: str) -> bool:
    if not run_id or not session_id or session_id not in run_id:
        return False
    run = _as_dict(authority.get("run"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    final_truth = _as_dict(authority.get("final_truth"))
    request = _as_dict(authority.get("approval_request"))
    return (
        run.get("run_id") == run_id
        and request.get("control_plane_target_ref") == run_id
        and run_id in str(checkpoint.get("checkpoint_id") or "")
        and run_id in str(final_truth.get("final_truth_record_id") or "")
    )


def _verdict_signature_material(checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_VERDICT_SCHEMA_VERSION,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "expected_output_path": PRODUCTFLOW_OUTPUT_PATH,
        "expected_output_content": PRODUCTFLOW_OUTPUT_CONTENT,
        "expected_issue_status": EXPECTED_ISSUE_STATUS,
        "expected_approval_reason": APPROVAL_REASON,
        "checks": {str(check["id"]): str(check["status"]) for check in checks},
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
    }


def _campaign_failures(
    *,
    clean_reports: list[dict[str, Any]],
    stable: bool,
    digests: set[str],
    invariant_digests: set[str],
    substrate_digests: set[str],
    side_effect_free: bool,
) -> list[str]:
    if stable:
        return []
    failures: list[str] = []
    if len(clean_reports) < 2:
        failures.append("repeat_evidence_missing")
    if any(report.get("observed_result") != "success" for report in clean_reports):
        failures.append("bundle_verification_failed")
    if len(digests) != 1:
        failures.append("verdict_signature_not_stable")
    if len(invariant_digests) != 1:
        failures.append("invariant_model_signature_not_stable")
    if len(substrate_digests) != 1:
        failures.append("substrate_signature_not_stable")
    if not side_effect_free:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    return failures


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _without_diff_ledger(value: Any) -> Any:
    copied = copy.deepcopy(value)
    if isinstance(copied, dict):
        copied.pop("diff_ledger", None)
        return copied
    return copied


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
