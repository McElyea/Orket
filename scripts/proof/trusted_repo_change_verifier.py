from __future__ import annotations

import copy
from typing import Any

from scripts.proof.trusted_repo_change_contract import (
    APPROVAL_REASON,
    BUNDLE_SCHEMA_VERSION,
    CONFIG_ARTIFACT_PATH,
    CONTRACT_VERDICT_SCHEMA_VERSION,
    FALLBACK_CLAIM_TIER,
    MUST_CATCH_OUTCOMES,
    OPERATOR_SURFACE,
    REPORT_SCHEMA_VERSION,
    RESOURCE_ID,
    TARGET_CLAIM_TIER,
    TRUSTED_REPO_COMPARE_SCOPE,
    VALIDATOR_SCHEMA_VERSION,
    build_contract_verdict,
    now_utc_iso,
    stable_json_digest,
)
from scripts.proof.trusted_scope_family_support import (
    ValidatorBackedScopeConfig,
    build_bundle_verification_failures,
    build_validator_backed_campaign_report,
)

INVARIANT_MODEL_SCHEMA_VERSION = "trusted_run_invariant_model.v1"
SUBSTRATE_SCHEMA_VERSION = "control_plane_witness_substrate.v1"
_CONFIG = ValidatorBackedScopeConfig(
    compare_scope=TRUSTED_REPO_COMPARE_SCOPE,
    operator_surface=OPERATOR_SURFACE,
    fallback_claim_tier=FALLBACK_CLAIM_TIER,
    target_claim_tier=TARGET_CLAIM_TIER,
    bundle_schema_version=BUNDLE_SCHEMA_VERSION,
    report_schema_version=REPORT_SCHEMA_VERSION,
)


def evaluate_trusted_repo_change_invariants(bundle: dict[str, Any]) -> dict[str, Any]:
    authority = _as_dict(bundle.get("authority_lineage"))
    observed = _as_dict(bundle.get("observed_effect"))
    validator = _as_dict(bundle.get("validator_result"))
    verdict = _as_dict(bundle.get("contract_verdict"))
    run_id = _text(bundle.get("run_id"))
    session_id = _text(bundle.get("session_id"))
    failures: list[str] = []
    checks: list[dict[str, str]] = []

    def check(check_id: str, passed: bool, failure: str, basis: str) -> None:
        checks.append({"id": check_id, "status": "pass" if passed else "fail", "failure": "" if passed else failure, "basis": basis})
        if not passed:
            _append_unique(failures, failure)

    check("TRC-INV-001", bundle.get("schema_version") == BUNDLE_SCHEMA_VERSION, "schema_version_missing_or_unsupported", "bundle schema")
    check("TRC-INV-002", bundle.get("compare_scope") == TRUSTED_REPO_COMPARE_SCOPE, "compare_scope_missing_or_unsupported", "compare scope")
    check("TRC-INV-003", bundle.get("operator_surface") == OPERATOR_SURFACE, "operator_surface_missing", "operator surface")
    check("TRC-INV-004", session_id in run_id and run_id.startswith("trusted-repo-run:"), "canonical_run_id_drift", "canonical run id")
    check("TRC-INV-005", _policy_configuration_ok(bundle, authority), "policy_or_configuration_missing", "policy and config")
    check("TRC-INV-006", _governed_input_ok(authority), "governed_input_missing", "governed input")
    check("TRC-INV-007", _run_lineage_ok(authority, run_id), "canonical_run_id_drift", "run lineage")
    check("TRC-INV-008", _attempt_ok(authority), "attempt_authority_missing", "attempt authority")
    check("TRC-INV-009", _approval_request_ok(authority, run_id), "missing_approval_resolution", "approval request")
    check("TRC-INV-010", _operator_action_ok(authority, run_id), "missing_approval_resolution", "approval action")
    check("TRC-INV-011", _checkpoint_ok(authority, run_id), "checkpoint_missing_or_drifted", "checkpoint")
    check("TRC-INV-012", _reservation_and_lease_ok(authority, run_id), "resource_or_lease_evidence_missing", "reservation and lease")
    check("TRC-INV-013", _effect_journal_ok(authority), "missing_effect_evidence", "effect journal")
    check("TRC-INV-014", observed.get("actual_output_artifact_path") == CONFIG_ARTIFACT_PATH, "missing_config_artifact", "bounded output")
    check("TRC-INV-015", not observed.get("forbidden_mutations"), "forbidden_path_mutation", "path boundary")
    check("TRC-INV-016", validator.get("schema_version") == VALIDATOR_SCHEMA_VERSION, "missing_validator_result", "validator result")
    check("TRC-INV-017", validator.get("validation_result") == "pass", "validator_failed", "validator pass")
    check("TRC-INV-018", _final_truth_success_ok(authority), "missing_final_truth", "final truth")
    check("TRC-INV-019", verdict.get("schema_version") == CONTRACT_VERDICT_SCHEMA_VERSION, "contract_verdict_missing", "contract verdict")
    check("TRC-INV-020", bundle.get("claim_tier") == FALLBACK_CLAIM_TIER, "single_bundle_claim_tier_must_be_lab_only", "single bundle claim")
    check("TRC-INV-021", bundle.get("claim_tier") != "replay_deterministic", "replay_evidence_missing", "replay guard")
    check("TRC-INV-022", bundle.get("claim_tier") != "text_deterministic", "text_identity_evidence_missing", "text guard")

    result = "pass" if not failures else "fail"
    signature_material = {
        "schema_version": INVARIANT_MODEL_SCHEMA_VERSION,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "invariants": {item["id"]: item["status"] for item in checks},
        "failures": sorted(failures),
    }
    return {
        "schema_version": INVARIANT_MODEL_SCHEMA_VERSION,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "result": result,
        "checked_invariants": checks,
        "failures": failures,
        "missing_proof_blockers": [],
        "transition_trace": _transition_trace(checks),
        "invariant_signature_digest": stable_json_digest(signature_material),
    }


def evaluate_trusted_repo_change_substrate(bundle: dict[str, Any]) -> dict[str, Any]:
    authority = _as_dict(bundle.get("authority_lineage"))
    observed = _as_dict(bundle.get("observed_effect"))
    validator = _as_dict(bundle.get("validator_result"))
    verdict = _as_dict(bundle.get("contract_verdict"))
    run_id = _text(bundle.get("run_id"))
    failures: list[str] = []
    rows: list[dict[str, str]] = []

    def row(family: str, classification: str, passed: bool, failure: str, question: str) -> None:
        rows.append({"record_family": family, "classification": classification, "status": "pass" if passed else "fail", "failure": "" if passed else failure, "verifier_question": question})
        if not passed:
            _append_unique(failures, failure)

    row("governed_input", "required_authority", _governed_input_ok(authority), "governed_input_missing", "What was requested?")
    row("policy_snapshot", "required_authority", _policy_configuration_ok(bundle, authority), "policy_or_configuration_missing", "What policy admitted the run?")
    row("configuration_snapshot", "required_authority", bool(_text(bundle.get("configuration_snapshot_ref"))), "policy_or_configuration_missing", "Which config snapshot applied?")
    row("run", "required_authority", _run_lineage_ok(authority, run_id), "canonical_run_id_drift", "Which run is canonical?")
    row("attempt", "required_authority", _attempt_ok(authority), "attempt_authority_missing", "Which attempt was current?")
    row("approval_request", "required_authority", _approval_request_ok(authority, run_id), "missing_approval_resolution", "Was approval requested?")
    row("operator_action", "required_authority", _operator_action_ok(authority, run_id), "missing_approval_resolution", "Did an operator approve?")
    row("checkpoint_acceptance", "required_authority", _checkpoint_ok(authority, run_id), "checkpoint_missing_or_drifted", "Was continuation accepted?")
    row("reservation", "required_authority", _reservation_and_lease_ok(authority, run_id), "resource_or_lease_evidence_missing", "Who reserved the path?")
    row("lease", "required_authority", _reservation_and_lease_ok(authority, run_id), "resource_or_lease_evidence_missing", "Who owned the path?")
    row("resource", "required_authority", _resource_ok(authority), "resource_or_lease_evidence_missing", "Does resource authority match?")
    row("effect_journal", "required_authority", _effect_journal_ok(authority), "missing_effect_evidence", "What effect occurred?")
    row("output_artifact", "required_authority", observed.get("output_exists") is True, "missing_config_artifact", "What changed?")
    row("validator_result", "required_authority", validator.get("validation_result") == "pass", "validator_failed", "Did deterministic validation pass?")
    row("final_truth", "required_authority", _final_truth_success_ok(authority), "missing_final_truth", "What terminal truth was assigned?")
    row("contract_verdict", "required_authority", verdict.get("verdict") == "pass", "contract_verdict_missing", "Did the verdict pass?")
    row("run_summary", "projection_only", True, "", "Where are support artifacts?")
    row("human_summary", "projection_only", True, "", "What should a human inspect?")

    result = "pass" if not failures else "fail"
    signature_material = {
        "schema_version": SUBSTRATE_SCHEMA_VERSION,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "families": {item["record_family"]: item["status"] for item in rows},
        "classifications": {item["record_family"]: item["classification"] for item in rows},
        "failures": sorted(failures),
    }
    return {
        "schema_version": SUBSTRATE_SCHEMA_VERSION,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "result": result,
        "record_families": rows,
        "failures": failures,
        "missing_substrate_blockers": [],
        "substrate_signature_digest": stable_json_digest(signature_material),
    }


def verify_trusted_repo_change_bundle_payload(bundle: dict[str, Any], *, evidence_ref: str = "") -> dict[str, Any]:
    from scripts.proof.trusted_run_proof_foundation import evaluate_offline_verifier_non_interference

    clean = _without_diff_ledger(bundle)
    included_verdict = _as_dict(clean.get("contract_verdict"))
    recomputed = build_contract_verdict(clean)
    invariant_model = evaluate_trusted_repo_change_invariants(clean)
    substrate_model = evaluate_trusted_repo_change_substrate(clean)
    non_interference = evaluate_offline_verifier_non_interference()
    failures = build_bundle_verification_failures(
        included_verdict,
        recomputed,
        invariant_model,
        substrate_model,
        side_effect_free=non_interference.get("result") == "pass",
    )
    validator = _as_dict(clean.get("validator_result"))
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary" if clean.get("schema_version") == BUNDLE_SCHEMA_VERSION else "blocked",
        "observed_result": "success" if not failures else "failure",
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "bundle_id": _text(clean.get("bundle_id")),
        "run_id": _text(clean.get("run_id")),
        "session_id": _text(clean.get("session_id")),
        "policy_digest": _text(clean.get("policy_digest")),
        "control_bundle_ref": _text(clean.get("control_bundle_ref")),
        "evidence_ref": evidence_ref,
        "side_effect_free_verification": non_interference.get("result") == "pass",
        "contract_verdict": recomputed,
        "trusted_run_invariant_model": invariant_model,
        "control_plane_witness_substrate": substrate_model,
        "offline_verifier_non_interference_signature_digest": _text(
            non_interference.get("non_interference_signature_digest")
        ),
        "validator_signature_digest": _text(validator.get("validator_signature_digest")),
        "included_contract_verdict_digest": _text(included_verdict.get("verdict_signature_digest")),
        "recomputed_contract_verdict_digest": _text(recomputed.get("verdict_signature_digest")),
        "invariant_model_signature_digest": _text(invariant_model.get("invariant_signature_digest")),
        "substrate_signature_digest": _text(substrate_model.get("substrate_signature_digest")),
        "missing_evidence": failures,
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
    }


def build_trusted_repo_change_campaign_report(
    reports: list[dict[str, Any]],
    *,
    bundle_refs: list[str] | None = None,
    live_proof_refs: list[str] | None = None,
) -> dict[str, Any]:
    return build_validator_backed_campaign_report(
        reports,
        config=_CONFIG,
        must_catch_outcomes=list(MUST_CATCH_OUTCOMES),
        bundle_refs=bundle_refs,
        live_proof_refs=live_proof_refs,
    )


def _transition_trace(checks: list[dict[str, str]]) -> list[dict[str, str]]:
    groups = {
        "admit_run": ("TRC-INV-004", "TRC-INV-005", "TRC-INV-006"),
        "publish_checkpoint": ("TRC-INV-011",),
        "resolve_approval": ("TRC-INV-009", "TRC-INV-010"),
        "publish_effect": ("TRC-INV-012", "TRC-INV-013", "TRC-INV-014", "TRC-INV-015"),
        "validate_artifact": ("TRC-INV-016", "TRC-INV-017"),
        "publish_final_truth": ("TRC-INV-018",),
        "verify_bundle": ("TRC-INV-019", "TRC-INV-020", "TRC-INV-021", "TRC-INV-022"),
    }
    statuses = {item["id"]: item["status"] for item in checks}
    return [{"transition": name, "status": "pass" if all(statuses.get(item) == "pass" for item in ids) else "fail"} for name, ids in groups.items()]


def _policy_configuration_ok(bundle: dict[str, Any], authority: dict[str, Any]) -> bool:
    run = _as_dict(authority.get("run"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    return bool(_text(bundle.get("policy_digest"))) and bool(_text(run.get("policy_snapshot_id"))) and bool(_text(checkpoint.get("policy_digest")))


def _governed_input_ok(authority: dict[str, Any]) -> bool:
    source = _as_dict(authority.get("governed_input"))
    return source.get("change_id") == "TRUSTED-CHANGE-1" and source.get("artifact_path") == CONFIG_ARTIFACT_PATH


def _run_lineage_ok(authority: dict[str, Any], run_id: str) -> bool:
    run = _as_dict(authority.get("run"))
    truth = _as_dict(authority.get("final_truth"))
    return run.get("run_id") == run_id and run.get("final_truth_record_id") == truth.get("final_truth_record_id")


def _attempt_ok(authority: dict[str, Any]) -> bool:
    run = _as_dict(authority.get("run"))
    return bool(_text(run.get("current_attempt_id"))) and bool(_text(run.get("current_attempt_state")))


def _approval_request_ok(authority: dict[str, Any], run_id: str) -> bool:
    request = _as_dict(authority.get("approval_request"))
    return request.get("reason") == APPROVAL_REASON and request.get("control_plane_target_ref") == run_id


def _operator_action_ok(authority: dict[str, Any], run_id: str) -> bool:
    action = _as_dict(authority.get("operator_action"))
    return _text(action.get("result")).lower() == "approved" and run_id in [_text(item) for item in action.get("affected_resource_refs") or []]


def _checkpoint_ok(authority: dict[str, Any], run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    return run_id in _text(checkpoint.get("checkpoint_id")) and checkpoint.get("acceptance_outcome") == "checkpoint_accepted"


def _reservation_and_lease_ok(authority: dict[str, Any], run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    reservation = _as_dict(authority.get("reservation"))
    refs = list(checkpoint.get("acceptance_dependent_reservation_refs") or []) + list(checkpoint.get("acceptance_dependent_lease_refs") or [])
    return any(run_id in _text(ref) for ref in refs) and run_id in " ".join(_text(value) for value in reservation.values())


def _resource_ok(authority: dict[str, Any]) -> bool:
    resource = _as_dict(authority.get("resource"))
    return resource.get("resource_id") == RESOURCE_ID and CONFIG_ARTIFACT_PATH in _text(resource.get("current_observed_state"))


def _effect_journal_ok(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    return int(journal.get("effect_entry_count") or 0) >= 1 and journal.get("latest_uncertainty_classification") == "no_residual_uncertainty"


def _final_truth_success_ok(authority: dict[str, Any]) -> bool:
    truth = _as_dict(authority.get("final_truth"))
    return truth.get("result_class") == "success" and truth.get("evidence_sufficiency_classification") == "evidence_sufficient"


def _without_diff_ledger(value: Any) -> dict[str, Any]:
    copied = copy.deepcopy(value)
    if isinstance(copied, dict):
        copied.pop("diff_ledger", None)
        return copied
    return {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append_unique(result, value)
    return result
