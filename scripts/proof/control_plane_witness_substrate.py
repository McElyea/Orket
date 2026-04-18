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
    COMPARE_SCOPE,
    CONTRACT_VERDICT_SCHEMA_VERSION,
    EXPECTED_ISSUE_STATUS,
    OPERATOR_SURFACE,
    stable_json_digest,
)

SUBSTRATE_SCHEMA_VERSION = "control_plane_witness_substrate.v1"


def evaluate_control_plane_witness_substrate(bundle: dict[str, Any]) -> dict[str, Any]:
    authority = _as_dict(bundle.get("authority_lineage"))
    observed = _as_dict(bundle.get("observed_effect"))
    verdict = _as_dict(bundle.get("contract_verdict"))
    run_id = _text(bundle.get("run_id"))
    session_id = _text(bundle.get("session_id"))
    expected_resource = f"namespace:issue:{PRODUCTFLOW_ISSUE_ID}"
    failures: list[str] = []
    blockers: list[str] = []
    rows: list[dict[str, str]] = []

    def row(family: str, classification: str, passed: bool, failure: str, question: str) -> None:
        status = "pass" if passed else "fail"
        rows.append(
            {
                "record_family": family,
                "classification": classification,
                "status": status,
                "failure": "" if passed else failure,
                "verifier_question": question,
            }
        )
        if not passed:
            _append_unique(failures, failure)

    row("governed_input", "required_authority", _governed_input_ok(authority), "governed_input_missing", "What request was admitted?")
    row("workload_catalog", "optional_supporting_evidence", True, "", "Which governed start path admitted the work?")
    row("policy_snapshot", "required_authority", _policy_ok(bundle, authority), "policy_or_configuration_missing", "Which policy admitted the run?")
    row("configuration_snapshot", "required_authority", _configuration_ok(bundle, authority), "policy_or_configuration_missing", "Which configuration admitted the run?")
    row("run", "required_authority", _run_ok(authority, run_id, session_id), "canonical_run_id_drift", "Which governed run is canonical?")
    row("attempt", "authority_preserving_projection", _attempt_ok(authority), "step_lineage_missing_or_drifted", "Which attempt was current?")
    row("step", "required_authority", _step_ok(authority), "step_lineage_missing_or_drifted", "Which step explains the effect?")
    row("approval_request", "required_authority", _approval_request_ok(authority, run_id), "approval_request_missing_or_drifted", "Was approval requested?")
    row("operator_action", "required_authority", _operator_action_ok(authority, run_id), "missing_approval_resolution", "Did an operator approve?")
    row("checkpoint_acceptance", "required_authority", _checkpoint_ok(authority, run_id), "checkpoint_missing_or_drifted", "Was continuation accepted?")
    row("reservation", "required_authority", _reservation_ok(authority, run_id), "lease_source_reservation_not_verified", "Who reserved the namespace?")
    row("lease", "authority_preserving_projection", _lease_ok(authority, run_id), "resource_or_lease_evidence_missing", "Who owned the namespace?")
    row("resource", "required_authority", _resource_ok(authority, expected_resource), "resource_lease_consistency_not_verified", "Does resource authority agree with lease?")
    row("effect_journal", "required_authority", _effect_journal_ok(authority), "missing_effect_evidence", "What effect was authorized and observed?")
    row("final_truth", "required_authority", _final_truth_ok(authority, run_id), "missing_final_truth", "What terminal result was assigned?")
    row("bounded_output_artifact", "required_authority", _output_artifact_ok(bundle, observed), "artifact_ref_missing", "Does bounded filesystem evidence match?")
    row("issue_state_read_model", "authority_preserving_projection", observed.get("issue_status") == EXPECTED_ISSUE_STATUS, "wrong_terminal_issue_status", "Did issue state reach terminal status?")
    row("contract_verdict", "required_authority", _contract_verdict_ok(verdict), "contract_verdict_missing", "Did deterministic verdict pass?")
    row("invariant_model", "required_authority", True, "", "Do invariant checks pass on the same evidence?")
    row("verifier_report", "required_authority_for_campaign_only", True, "", "Did bundle verification succeed?")
    row("campaign_report", "optional_supporting_evidence", True, "", "Are repeated verifier reports stable?")
    row("run_summary", "projection_only", True, "", "Where are support artifacts?")
    row("review_package", "projection_only", True, "", "What should a human inspect?")
    row("evidence_graph", "projection_only", True, "", "How is evidence visualized?")
    row("packet_blocks", "projection_only", True, "", "What is the operator summary?")
    row("model_text_semantics", "out_of_scope", True, "", "Was generated text semantically good?")

    if _projection_without_source_ref(bundle):
        _append_unique(blockers, "authority_source_ref_missing")
    if _projection_substitute_present(bundle, authority, observed):
        _append_unique(blockers, "projection_substitute_not_authority")

    result = "pass" if not failures and not blockers else "fail"
    signature_material = {
        "schema_version": SUBSTRATE_SCHEMA_VERSION,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "families": {item["record_family"]: item["status"] for item in rows},
        "classifications": {item["record_family"]: item["classification"] for item in rows},
        "failures": sorted(failures),
        "missing_substrate_blockers": sorted(blockers),
    }
    return {
        "schema_version": SUBSTRATE_SCHEMA_VERSION,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "result": result,
        "record_families": rows,
        "failures": failures,
        "missing_substrate_blockers": blockers,
        "substrate_signature_digest": stable_json_digest(signature_material),
    }


def _governed_input_ok(authority: dict[str, Any]) -> bool:
    source = _as_dict(authority.get("governed_input"))
    return (
        source.get("epic_id") == PRODUCTFLOW_EPIC_ID
        and source.get("issue_id") == PRODUCTFLOW_ISSUE_ID
        and source.get("seat") == PRODUCTFLOW_BUILDER_SEAT
        and bool(_text(source.get("payload_digest")))
    )


def _policy_ok(bundle: dict[str, Any], authority: dict[str, Any]) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    return bool(_text(bundle.get("policy_digest"))) and bool(
        _text(checkpoint.get("policy_digest") or checkpoint.get("acceptance_evaluated_policy_digest"))
    )


def _configuration_ok(bundle: dict[str, Any], authority: dict[str, Any]) -> bool:
    run = _as_dict(authority.get("run"))
    return bool(_text(bundle.get("configuration_snapshot_ref"))) and bool(_text(run.get("configuration_snapshot_id")))


def _run_ok(authority: dict[str, Any], run_id: str, session_id: str) -> bool:
    run = _as_dict(authority.get("run"))
    return bool(run_id) and run_id != session_id and session_id in run_id and run.get("run_id") == run_id


def _attempt_ok(authority: dict[str, Any]) -> bool:
    run = _as_dict(authority.get("run"))
    return bool(_text(run.get("current_attempt_id"))) and bool(_text(run.get("current_attempt_state")))


def _step_ok(authority: dict[str, Any]) -> bool:
    step = _as_dict(authority.get("step"))
    journal = _as_dict(authority.get("effect_journal"))
    step_id = _text(step.get("latest_step_id"))
    journal_step_id = _text(journal.get("latest_step_id"))
    prior_entry = _text(journal.get("latest_prior_journal_entry_id"))
    return int(step.get("step_count") or 0) >= 1 and bool(step_id) and (journal_step_id == step_id or step_id in prior_entry)


def _approval_request_ok(authority: dict[str, Any], run_id: str) -> bool:
    request = _as_dict(authority.get("approval_request"))
    return request.get("reason") == APPROVAL_REASON and request.get("control_plane_target_ref") == run_id


def _operator_action_ok(authority: dict[str, Any], run_id: str) -> bool:
    action = _as_dict(authority.get("operator_action"))
    return _text(action.get("result")).lower() == "approved" and run_id in [_text(item) for item in action.get("affected_resource_refs") or []]


def _checkpoint_ok(authority: dict[str, Any], run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    return run_id in _text(checkpoint.get("checkpoint_id")) and checkpoint.get("acceptance_outcome") == "checkpoint_accepted"


def _reservation_ok(authority: dict[str, Any], run_id: str) -> bool:
    reservation = _as_dict(authority.get("reservation"))
    return bool(reservation) and run_id in " ".join(_text(value) for value in reservation.values())


def _lease_ok(authority: dict[str, Any], run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    refs = [_text(ref) for ref in checkpoint.get("acceptance_dependent_lease_refs") or []]
    return any(run_id in ref for ref in refs)


def _resource_ok(authority: dict[str, Any], expected_resource: str) -> bool:
    resource = _as_dict(authority.get("resource"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    lease_refs = {_text(ref) for ref in checkpoint.get("acceptance_dependent_lease_refs") or []}
    observed_state = _text(resource.get("current_observed_state"))
    return resource.get("resource_id") == expected_resource and resource.get("provenance_ref") in lease_refs and expected_resource in observed_state


def _effect_journal_ok(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    return (
        int(journal.get("effect_entry_count") or 0) >= 2
        and bool(_text(journal.get("latest_authorization_basis_ref")))
        and bool(_text(journal.get("latest_observed_result_ref")))
        and journal.get("latest_uncertainty_classification") == "no_residual_uncertainty"
    )


def _final_truth_ok(authority: dict[str, Any], run_id: str) -> bool:
    run = _as_dict(authority.get("run"))
    truth = _as_dict(authority.get("final_truth"))
    truth_id = _text(truth.get("final_truth_record_id"))
    return (
        bool(truth_id)
        and run.get("final_truth_record_id") == truth_id
        and run_id in truth_id
        and truth.get("result_class") == "success"
        and truth.get("evidence_sufficiency_classification") == "evidence_sufficient"
    )


def _output_artifact_ok(bundle: dict[str, Any], observed: dict[str, Any]) -> bool:
    refs = [ref for ref in bundle.get("artifact_refs") or [] if isinstance(ref, dict)]
    output_ref = next((ref for ref in refs if ref.get("kind") == "output_artifact"), {})
    return (
        output_ref.get("path") == PRODUCTFLOW_OUTPUT_PATH
        and _text(output_ref.get("digest")).startswith("sha256:")
        and observed.get("actual_output_artifact_path") == PRODUCTFLOW_OUTPUT_PATH
        and observed.get("normalized_content") == PRODUCTFLOW_OUTPUT_CONTENT
    )


def _contract_verdict_ok(verdict: dict[str, Any]) -> bool:
    return verdict.get("schema_version") == CONTRACT_VERDICT_SCHEMA_VERSION and verdict.get("verdict") == "pass"


def _projection_without_source_ref(bundle: dict[str, Any]) -> bool:
    projections = _as_dict(bundle.get("projection_evidence"))
    return any(isinstance(value, dict) and not _has_source_ref(value) for value in projections.values())


def _projection_substitute_present(bundle: dict[str, Any], authority: dict[str, Any], observed: dict[str, Any]) -> bool:
    projections = _as_dict(bundle.get("projection_evidence"))
    if projections and _missing_required_authority(authority):
        return True
    if not _as_dict(authority.get("final_truth")) and observed.get("issue_status") == EXPECTED_ISSUE_STATUS:
        return True
    if not _as_dict(authority.get("effect_journal")) and observed.get("normalized_content") == PRODUCTFLOW_OUTPUT_CONTENT:
        return True
    return False


def _missing_required_authority(authority: dict[str, Any]) -> bool:
    for family in ("governed_input", "run", "step", "approval_request", "operator_action", "checkpoint", "reservation", "resource", "effect_journal", "final_truth"):
        if not _as_dict(authority.get(family)):
            return True
    return False


def _has_source_ref(value: dict[str, Any]) -> bool:
    return any(bool(_text(value.get(key))) for key in ("source_ref", "source_path", "source_id", "digest")) or bool(value.get("source_record_refs"))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)
