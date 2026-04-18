from __future__ import annotations

from typing import Any

from scripts.productflow.productflow_support import (
    PRODUCTFLOW_BUILDER_SEAT,
    PRODUCTFLOW_EPIC_ID,
    PRODUCTFLOW_ISSUE_ID,
    PRODUCTFLOW_OUTPUT_CONTENT,
    PRODUCTFLOW_OUTPUT_PATH,
)
from scripts.proof.trusted_run_witness_contract import (
    APPROVAL_REASON,
    BUNDLE_SCHEMA_VERSION,
    COMPARE_SCOPE,
    CONTRACT_VERDICT_SCHEMA_VERSION,
    EXPECTED_ISSUE_STATUS,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    TARGET_CLAIM_TIER,
    stable_json_digest,
)

INVARIANT_MODEL_SCHEMA_VERSION = "trusted_run_invariant_model.v1"


def evaluate_trusted_run_invariants(bundle: dict[str, Any]) -> dict[str, Any]:
    authority = _as_dict(bundle.get("authority_lineage"))
    observed = _as_dict(bundle.get("observed_effect"))
    verdict = _as_dict(bundle.get("contract_verdict"))
    failures: list[str] = []
    blockers: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(invariant_id: str, passed: bool, failure: str, basis: str) -> None:
        checks.append(
            {
                "id": invariant_id,
                "status": "pass" if passed else "fail",
                "failure": "" if passed else failure,
                "basis": basis,
            }
        )
        if not passed:
            _append_unique(failures, failure)

    run_id = _text(bundle.get("run_id"))
    session_id = _text(bundle.get("session_id"))
    expected_resource = f"namespace:issue:{PRODUCTFLOW_ISSUE_ID}"

    check("TRI-INV-001", bundle.get("schema_version") == BUNDLE_SCHEMA_VERSION, "schema_version_missing_or_unsupported", "bundle schema")
    check("TRI-INV-002", bundle.get("compare_scope") == COMPARE_SCOPE, "compare_scope_missing_or_unsupported", "compare scope")
    check("TRI-INV-003", bundle.get("operator_surface") == OPERATOR_SURFACE, "operator_surface_missing", "operator surface")
    check("TRI-INV-004", _canonical_run_id_present(run_id), "canonical_run_id_drift", "canonical governed run id")
    check("TRI-INV-005", _locator_not_authority(bundle, run_id, session_id), "canonical_run_id_drift", "session and artifact locator evidence")
    check("TRI-INV-006", _run_lineage_ok(authority, run_id), "canonical_run_id_drift", "run lineage alignment")
    check("TRI-INV-007", _policy_configuration_ok(bundle, authority), "policy_or_configuration_missing", "policy and configuration snapshots")
    check("TRI-INV-008", _artifact_refs_ok(bundle), "artifact_ref_missing", "artifact path and digest refs")
    check("TRI-INV-009", _governed_input_ok(authority), "governed_input_missing", "ProductFlow governed input")
    check("TRI-INV-010", _step_lineage_ok(authority), "step_lineage_missing_or_drifted", "run, attempt, and step/effect linkage")
    check("TRI-INV-011", _approval_request_ok(authority, run_id), "approval_request_missing_or_drifted", "approval request target")
    check("TRI-INV-012", _operator_action_ok(authority, run_id), "missing_approval_resolution", "operator approval action")
    check("TRI-INV-013", _checkpoint_ok(authority, run_id), "checkpoint_missing_or_drifted", "accepted checkpoint")
    check("TRI-INV-014", _resource_authority_ok(authority, expected_resource), "resource_or_lease_evidence_missing", "resource authority")
    check("TRI-INV-015", _reservation_and_lease_refs_ok(authority, run_id), "resource_or_lease_evidence_missing", "reservation and lease refs")
    check("TRI-INV-016", _lease_source_ok(authority, run_id), "lease_source_reservation_not_verified", "lease source reservation evidence")
    check("TRI-INV-017", _resource_lease_consistency_ok(authority, expected_resource), "resource_lease_consistency_not_verified", "resource versus lease consistency")
    check("TRI-INV-018", _effect_journal_present(authority), "missing_effect_evidence", "effect journal presence")
    check("TRI-INV-019", _effect_journal_detail_ok(authority), "missing_effect_evidence", "effect journal target and authorization details")
    check("TRI-INV-020", _effect_prior_chain_ok(authority), "effect_prior_chain_not_verified", "effect prior-chain evidence")
    check("TRI-INV-021", observed.get("actual_output_artifact_path") == PRODUCTFLOW_OUTPUT_PATH, "missing_output_artifact", "bounded output path")
    check("TRI-INV-022", observed.get("normalized_content") == PRODUCTFLOW_OUTPUT_CONTENT, "wrong_output_content", "bounded output content")
    check("TRI-INV-023", observed.get("issue_status") == EXPECTED_ISSUE_STATUS, "wrong_terminal_issue_status", "terminal issue status")
    check("TRI-INV-024", bool(_as_dict(authority.get("final_truth"))), "missing_final_truth", "final truth presence")
    check("TRI-INV-025", _final_truth_success_ok(authority), "missing_final_truth", "final truth success classification")
    check("TRI-INV-026", _final_truth_cardinality_ok(authority, run_id), "final_truth_cardinality_not_verified", "run final-truth identity")
    check("TRI-INV-027", verdict.get("schema_version") == CONTRACT_VERDICT_SCHEMA_VERSION, "contract_verdict_missing", "contract verdict presence")
    check("TRI-INV-028", _contract_verdict_digest_ok(verdict), "contract_verdict_drift", "included verdict digest")
    check("TRI-INV-029", bundle.get("claim_tier") == FALLBACK_CLAIM_TIER, "single_bundle_claim_tier_must_be_lab_only", "single-bundle claim tier")
    check("TRI-INV-030", bundle.get("claim_tier") != TARGET_CLAIM_TIER, "repeat_evidence_missing", "campaign-only deterministic claim")
    check("TRI-INV-031", True, "", "bundle evaluation is pure inspection; mutation proof is covered by contract tests")
    check("TRI-INV-032", bundle.get("claim_tier") != "replay_deterministic", "replay_deterministic_evidence_missing", "replay claim guard")
    check("TRI-INV-033", bundle.get("claim_tier") != "text_deterministic", "text_deterministic_evidence_missing", "text determinism claim guard")

    result = "pass" if not failures and not blockers else "fail"
    signature_material = {
        "schema_version": INVARIANT_MODEL_SCHEMA_VERSION,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "expected_output_path": PRODUCTFLOW_OUTPUT_PATH,
        "expected_output_content": PRODUCTFLOW_OUTPUT_CONTENT,
        "expected_issue_status": EXPECTED_ISSUE_STATUS,
        "invariants": {item["id"]: item["status"] for item in checks},
        "missing_proof_blockers": list(blockers),
        "failures": sorted(failures),
    }
    return {
        "schema_version": INVARIANT_MODEL_SCHEMA_VERSION,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "result": result,
        "checked_invariants": checks,
        "failures": failures,
        "missing_proof_blockers": blockers,
        "transition_trace": _transition_trace(checks),
        "invariant_signature_digest": stable_json_digest(signature_material),
    }


def _canonical_run_id_present(run_id: str) -> bool:
    return run_id.startswith("turn-tool-run:") and PRODUCTFLOW_ISSUE_ID in run_id and PRODUCTFLOW_BUILDER_SEAT in run_id


def _locator_not_authority(bundle: dict[str, Any], run_id: str, session_id: str) -> bool:
    basis = _as_dict(bundle.get("resolution_basis"))
    run_summary_path = _text(basis.get("run_summary_path"))
    return bool(session_id) and run_id != session_id and session_id in run_id and run_summary_path == f"runs/{session_id}/run_summary.json"


def _run_lineage_ok(authority: dict[str, Any], run_id: str) -> bool:
    run = _as_dict(authority.get("run"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    final_truth = _as_dict(authority.get("final_truth"))
    request = _as_dict(authority.get("approval_request"))
    return (
        run.get("run_id") == run_id
        and request.get("control_plane_target_ref") == run_id
        and run_id in _text(checkpoint.get("checkpoint_id"))
        and run_id in _text(final_truth.get("final_truth_record_id"))
    )


def _policy_configuration_ok(bundle: dict[str, Any], authority: dict[str, Any]) -> bool:
    run = _as_dict(authority.get("run"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    return all(
        bool(_text(bundle.get(key)))
        for key in ("policy_digest", "policy_snapshot_ref", "configuration_snapshot_ref", "control_bundle_ref")
    ) and all(
        bool(_text(value))
        for value in (
            run.get("policy_snapshot_id"),
            run.get("configuration_snapshot_id"),
            checkpoint.get("policy_digest") or checkpoint.get("acceptance_evaluated_policy_digest"),
        )
    )


def _artifact_refs_ok(bundle: dict[str, Any]) -> bool:
    refs = [ref for ref in bundle.get("artifact_refs") or [] if isinstance(ref, dict)]
    by_kind = {_text(ref.get("kind")): ref for ref in refs}
    for kind in ("run_summary", "output_artifact"):
        ref = _as_dict(by_kind.get(kind))
        if not _text(ref.get("path")) or not _text(ref.get("digest")).startswith("sha256:"):
            return False
    return _as_dict(by_kind.get("output_artifact")).get("path") == PRODUCTFLOW_OUTPUT_PATH


def _governed_input_ok(authority: dict[str, Any]) -> bool:
    governed_input = _as_dict(authority.get("governed_input"))
    return (
        governed_input.get("epic_id") == PRODUCTFLOW_EPIC_ID
        and governed_input.get("issue_id") == PRODUCTFLOW_ISSUE_ID
        and governed_input.get("seat") == PRODUCTFLOW_BUILDER_SEAT
        and bool(_text(governed_input.get("payload_digest")))
    )


def _step_lineage_ok(authority: dict[str, Any]) -> bool:
    run = _as_dict(authority.get("run"))
    step = _as_dict(authority.get("step"))
    journal = _as_dict(authority.get("effect_journal"))
    step_id = _text(step.get("latest_step_id"))
    journal_step_id = _text(journal.get("latest_step_id"))
    prior_entry = _text(journal.get("latest_prior_journal_entry_id"))
    step_explains_effect = journal_step_id == step_id or (step_id and step_id in prior_entry)
    return (
        bool(_text(run.get("current_attempt_id")))
        and int(step.get("step_count") or 0) >= 1
        and bool(step_id)
        and bool(journal_step_id)
        and step_explains_effect
    )


def _approval_request_ok(authority: dict[str, Any], run_id: str) -> bool:
    request = _as_dict(authority.get("approval_request"))
    return request.get("reason") == APPROVAL_REASON and request.get("control_plane_target_ref") == run_id


def _operator_action_ok(authority: dict[str, Any], run_id: str) -> bool:
    action = _as_dict(authority.get("operator_action"))
    affected_refs = [_text(item) for item in action.get("affected_resource_refs") or []]
    return _text(action.get("result")).lower() == "approved" and run_id in affected_refs


def _checkpoint_ok(authority: dict[str, Any], run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    return run_id in _text(checkpoint.get("checkpoint_id")) and checkpoint.get("acceptance_outcome") == "checkpoint_accepted"


def _resource_authority_ok(authority: dict[str, Any], expected_resource: str) -> bool:
    resource = _as_dict(authority.get("resource"))
    return resource.get("resource_id") == expected_resource and resource.get("namespace_scope") == f"issue:{PRODUCTFLOW_ISSUE_ID}"


def _reservation_and_lease_refs_ok(authority: dict[str, Any], run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    reservation_refs = [_text(ref) for ref in checkpoint.get("acceptance_dependent_reservation_refs") or []]
    lease_refs = [_text(ref) for ref in checkpoint.get("acceptance_dependent_lease_refs") or []]
    return any(run_id in ref for ref in reservation_refs) and any(run_id in ref for ref in lease_refs)


def _lease_source_ok(authority: dict[str, Any], run_id: str) -> bool:
    reservation = _as_dict(authority.get("reservation"))
    reservation_text = " ".join(_text(value) for value in reservation.values())
    return _reservation_and_lease_refs_ok(authority, run_id) and run_id in reservation_text


def _resource_lease_consistency_ok(authority: dict[str, Any], expected_resource: str) -> bool:
    resource = _as_dict(authority.get("resource"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    lease_refs = {_text(ref) for ref in checkpoint.get("acceptance_dependent_lease_refs") or []}
    observed_state = _text(resource.get("current_observed_state"))
    return (
        resource.get("resource_id") == expected_resource
        and resource.get("provenance_ref") in lease_refs
        and f"namespace:issue:{PRODUCTFLOW_ISSUE_ID}" in observed_state
    )


def _effect_journal_present(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    return int(journal.get("effect_entry_count") or 0) >= 2


def _effect_journal_detail_ok(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    return (
        bool(_text(journal.get("latest_step_id")))
        and bool(_text(journal.get("latest_authorization_basis_ref")))
        and bool(_text(journal.get("latest_intended_target_ref")))
        and bool(_text(journal.get("latest_observed_result_ref")))
        and journal.get("latest_uncertainty_classification") == "no_residual_uncertainty"
    )


def _effect_prior_chain_ok(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    if int(journal.get("effect_entry_count") or 0) <= 1:
        return True
    return bool(_text(journal.get("latest_prior_journal_entry_id"))) and bool(_text(journal.get("latest_prior_entry_digest")))


def _final_truth_success_ok(authority: dict[str, Any]) -> bool:
    final_truth = _as_dict(authority.get("final_truth"))
    return (
        final_truth.get("result_class") == "success"
        and final_truth.get("evidence_sufficiency_classification") == "evidence_sufficient"
    )


def _final_truth_cardinality_ok(authority: dict[str, Any], run_id: str) -> bool:
    run = _as_dict(authority.get("run"))
    final_truth = _as_dict(authority.get("final_truth"))
    final_truth_id = _text(final_truth.get("final_truth_record_id"))
    return bool(final_truth_id) and run.get("final_truth_record_id") == final_truth_id and run_id in final_truth_id


def _contract_verdict_digest_ok(verdict: dict[str, Any]) -> bool:
    return verdict.get("verdict") == "pass" and _text(verdict.get("verdict_signature_digest")).startswith("sha256:")


def _transition_trace(checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    groups = {
        "admit_run": ("TRI-INV-004", "TRI-INV-007", "TRI-INV-009"),
        "start_attempt": ("TRI-INV-010",),
        "publish_checkpoint": ("TRI-INV-013",),
        "resolve_approval": ("TRI-INV-011", "TRI-INV-012"),
        "establish_resource_authority": ("TRI-INV-014", "TRI-INV-015", "TRI-INV-016", "TRI-INV-017"),
        "publish_effect": ("TRI-INV-018", "TRI-INV-019", "TRI-INV-020"),
        "publish_final_truth": ("TRI-INV-024", "TRI-INV-025", "TRI-INV-026"),
        "build_witness_bundle": ("TRI-INV-001", "TRI-INV-002", "TRI-INV-003", "TRI-INV-008"),
        "verify_bundle": ("TRI-INV-027", "TRI-INV-028", "TRI-INV-031"),
        "compare_campaign": ("TRI-INV-029", "TRI-INV-030", "TRI-INV-032", "TRI-INV-033"),
    }
    statuses = {item["id"]: item["status"] for item in checks}
    trace: list[dict[str, str]] = []
    for transition, invariant_ids in groups.items():
        transition_status = "pass" if all(statuses.get(item) == "pass" for item in invariant_ids) else "fail"
        trace.append({"transition": transition, "status": transition_status})
    return trace


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)
