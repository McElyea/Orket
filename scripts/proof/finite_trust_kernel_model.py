from __future__ import annotations

from typing import Any

from scripts.proof.offline_trusted_run_verifier import CLAIM_ORDER
from scripts.proof.trusted_repo_change_contract import (
    BUNDLE_SCHEMA_VERSION,
    CONFIG_ARTIFACT_PATH,
    FALLBACK_CLAIM_TIER,
    MUST_CATCH_OUTCOMES,
    OPERATOR_SURFACE,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    TRUSTED_REPO_COMPARE_SCOPE,
    VALIDATOR_SCHEMA_VERSION,
    build_contract_verdict,
    stable_json_digest,
)
from scripts.proof.trusted_repo_change_verifier import (
    evaluate_trusted_repo_change_invariants,
    evaluate_trusted_repo_change_substrate,
)
from scripts.proof.trusted_scope_family_common import as_dict, text, unique, without_diff_ledger

FINITE_TRUST_KERNEL_MODEL_SCHEMA_VERSION = "finite_trust_kernel_model.v1"
MODEL_SIGNATURE_ROLE = "claim_supporting_only_when_recorded_by_admitted_verifier"
BOUNDED_EFFECT_CLASS = "repo_config_change"

STATE_NAMES = ("no_admissible_bundle", "admitted_input_observed", "policy_and_configuration_observed", "approval_or_operator_decision_observed", "checkpoint_accepted", "resource_authority_established", "effect_evidence_observed", "validator_or_contract_verdict_observed", "final_truth_observed", "verifier_accepted", "verifier_rejected", "claim_downgraded")

TRANSITION_INVARIANTS = {
    "admit_run": ("TRC-INV-001", "TRC-INV-002", "TRC-INV-003", "TRC-INV-004", "TRC-INV-006"),
    "resolve_policy_and_configuration": ("TRC-INV-005",),
    "request_operator_decision": ("TRC-INV-009",),
    "resolve_operator_decision": ("TRC-INV-010",),
    "accept_checkpoint": ("TRC-INV-011",),
    "establish_resource_authority": ("TRC-INV-012",),
    "publish_effect_evidence": ("TRC-INV-013", "TRC-INV-014", "TRC-INV-015"),
    "publish_validator_or_contract_verdict": ("TRC-INV-016", "TRC-INV-017", "TRC-INV-019"),
    "publish_final_truth": ("TRC-INV-018",),
    "build_witness_bundle": ("TRC-INV-001", "TRC-INV-002", "TRC-INV-003", "TRC-INV-005"),
}

FORBIDDEN_TRANSITION_RULES = (
    ("success_without_final_truth", ("TRC-INV-018",), "missing_final_truth"),
    ("success_without_effect_evidence", ("TRC-INV-013", "TRC-INV-014"), "missing_effect_evidence"),
    ("success_without_required_approval", ("TRC-INV-009", "TRC-INV-010"), "missing_approval_resolution"),
    ("success_without_validator_success", ("TRC-INV-016", "TRC-INV-017"), "missing_validator_result"),
    ("claim_upgrade_without_repeat_replay_or_text_evidence", ("TRC-INV-020", "TRC-INV-021", "TRC-INV-022"), "unsupported_claim_request"),
)

REASON_CAUSES = {
    "schema_version_missing_or_unsupported": "malformed_evidence",
    "compare_scope_missing_or_unsupported": "contradictory_evidence",
    "compare_scope_mismatch": "contradictory_evidence",
    "operator_surface_missing": "missing_evidence",
    "operator_surface_mismatch": "contradictory_evidence",
    "policy_or_configuration_missing": "missing_evidence",
    "governed_input_missing": "missing_evidence",
    "attempt_authority_missing": "missing_evidence",
    "missing_approval_resolution": "missing_evidence",
    "checkpoint_missing_or_drifted": "contradictory_evidence",
    "resource_or_lease_evidence_missing": "missing_evidence",
    "missing_effect_evidence": "missing_evidence",
    "missing_config_artifact": "missing_evidence",
    "forbidden_path_mutation": "contradictory_evidence",
    "missing_validator_result": "missing_evidence",
    "validator_failed": "contradictory_evidence",
    "missing_final_truth": "missing_evidence",
    "contract_verdict_missing": "missing_evidence",
    "contract_verdict_drift": "contradictory_evidence",
    "canonical_run_id_drift": "contradictory_evidence",
    "bundle_verification_failed": "contradictory_evidence",
    "verifier_side_effect_absence_not_mechanically_proven": "missing_evidence",
    "repeat_evidence_missing": "unsupported_claim_request",
    "replay_evidence_missing": "unsupported_claim_request",
    "text_identity_evidence_missing": "unsupported_claim_request",
    "verdict_signature_not_stable": "contradictory_evidence",
    "validator_signature_not_stable": "contradictory_evidence",
    "invariant_model_signature_not_stable": "contradictory_evidence",
    "substrate_signature_not_stable": "contradictory_evidence",
    "must_catch_outcomes_not_stable": "contradictory_evidence",
    "campaign_verdict_not_successful": "contradictory_evidence",
    "stale_authority_not_excluded": "stale_evidence",
}


def evaluate_finite_trust_kernel_model(
    payload: dict[str, Any],
    *,
    input_mode: str = "auto",
    requested_claims: list[str] | None = None,
    evidence_ref: str = "",
) -> dict[str, Any]:
    clean = without_diff_ledger(payload)
    mode = _resolve_input_mode(clean, input_mode)
    requested = list(requested_claims or [])
    witness_reports = _witness_reports_for_mode(clean, mode)
    invariant_statuses = _aggregate_invariant_statuses(witness_reports)
    missing_evidence = _missing_evidence_for_mode(clean, mode, witness_reports)
    allowed_claims, forbidden_claims = _claim_ladder(clean, mode, witness_reports)
    unsupported_claims = [claim for claim in requested if claim not in CLAIM_ORDER]
    if unsupported_claims:
        missing_evidence.append("unsupported_claim_request")
        forbidden_claims.append(_forbidden("unsupported", ["unsupported_claim_request"]))
    selected_claim = _highest_allowed(allowed_claims) or FALLBACK_CLAIM_TIER
    requested_missing = [claim for claim in requested if claim not in allowed_claims]
    claim_status = "blocked" if not allowed_claims else ("downgraded" if requested_missing else "allowed")
    transitions = _transition_results(invariant_statuses, clean, mode, witness_reports, allowed_claims)
    forbidden_transitions = _forbidden_transition_results(invariant_statuses, requested_missing)
    states = _state_results(transitions, claim_status, mode)
    rejection_reasons = unique(missing_evidence + _failed_transition_reasons(transitions))
    claim_downgrade_reasons = _claim_downgrade_reasons(requested_missing)
    accepted = not rejection_reasons and bool(allowed_claims)
    downgraded = claim_status == "downgraded"
    model_result = "rejected" if not accepted and not downgraded else ("downgraded" if downgraded else "accepted")
    observed_result = "failure" if model_result == "rejected" else ("partial success" if downgraded else "success")
    observed_path = "blocked" if model_result == "rejected" else ("degraded" if downgraded else "primary")
    missing_proof_blockers = _missing_proof_blockers(clean, mode, witness_reports)
    normalized = _normalized_evidence(clean, mode=mode, invariant_statuses=invariant_statuses, missing_proof_blockers=missing_proof_blockers, forbidden_claims=forbidden_claims)
    signature_material = _model_signature_material(normalized)
    return {
        "schema_version": FINITE_TRUST_KERNEL_MODEL_SCHEMA_VERSION,
        "proof_kind": "structural",
        "input_mode": mode,
        "input_refs": [evidence_ref] if evidence_ref else [],
        "observed_path": observed_path,
        "observed_result": observed_result,
        "model_result": model_result,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "bounded_effect_class": BOUNDED_EFFECT_CLASS,
        "states": states,
        "transitions": transitions,
        "forbidden_transition_results": forbidden_transitions,
        "invariant_mapping": _invariant_mapping(),
        "invariant_statuses": invariant_statuses,
        "missing_evidence": rejection_reasons,
        "claim_downgrade_reasons": claim_downgrade_reasons,
        "failure_causes": _failure_causes(unique(rejection_reasons + claim_downgrade_reasons)),
        "claim_status": claim_status,
        "claim_tier": selected_claim,
        "allowed_claims": allowed_claims,
        "forbidden_claims": forbidden_claims,
        "signature_role": MODEL_SIGNATURE_ROLE,
        "authority_warning": "finite-model signatures do not replace witness, validator, offline verifier, or packet verifier authority",
        "canonical_normalization": normalized,
        "model_signature_digest": stable_json_digest(signature_material),
    }


def _resolve_input_mode(payload: dict[str, Any], input_mode: str) -> str:
    if input_mode != "auto":
        return input_mode
    if payload.get("schema_version") == BUNDLE_SCHEMA_VERSION:
        return "bundle"
    if payload.get("schema_version") == REPORT_SCHEMA_VERSION and ("run_count" in payload or "bundle_reports" in payload):
        return "campaign_report"
    if payload.get("schema_version") == REPORT_SCHEMA_VERSION:
        return "single_report"
    return "unsupported"


def _witness_reports_for_mode(payload: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    if mode == "bundle":
        return [_report_from_bundle(payload)]
    if mode == "single_report":
        return [payload]
    if mode == "campaign_report":
        return [item for item in payload.get("bundle_reports") or [] if isinstance(item, dict)]
    return []


def _report_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    clean = without_diff_ledger(bundle)
    invariant = evaluate_trusted_repo_change_invariants(clean)
    substrate = evaluate_trusted_repo_change_substrate(clean)
    verdict = build_contract_verdict(clean)
    included_verdict = as_dict(clean.get("contract_verdict"))
    missing = unique(_included_verdict_failures(included_verdict, verdict) + list(verdict.get("failures") or []) + list(invariant.get("failures") or []) + list(substrate.get("failures") or []))
    validator = as_dict(clean.get("validator_result"))
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "observed_result": "success" if not missing else "failure",
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "side_effect_free_verification": True,
        "contract_verdict": verdict,
        "trusted_run_invariant_model": invariant,
        "control_plane_witness_substrate": substrate,
        "validator_signature_digest": text(validator.get("validator_signature_digest")),
        "invariant_model_signature_digest": text(invariant.get("invariant_signature_digest")),
        "substrate_signature_digest": text(substrate.get("substrate_signature_digest")),
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
        "missing_evidence": missing,
    }


def _included_verdict_failures(included: dict[str, Any], recomputed: dict[str, Any]) -> list[str]:
    if not included:
        return ["contract_verdict_missing"]
    return ["contract_verdict_drift"] if text(included.get("verdict_signature_digest")) != text(recomputed.get("verdict_signature_digest")) else []


def _aggregate_invariant_statuses(reports: list[dict[str, Any]]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for report in reports:
        invariant = as_dict(report.get("trusted_run_invariant_model"))
        for item in invariant.get("checked_invariants") or []:
            if not isinstance(item, dict):
                continue
            invariant_id = text(item.get("id"))
            status = text(item.get("status")) or "missing"
            if invariant_id and statuses.get(invariant_id, "pass") == "pass":
                statuses[invariant_id] = status
    return {key: statuses[key] for key in sorted(statuses)}


def _missing_evidence_for_mode(payload: dict[str, Any], mode: str, reports: list[dict[str, Any]]) -> list[str]:
    if mode == "unsupported":
        return ["schema_version_missing_or_unsupported"]
    failures: list[str] = []
    if payload.get("compare_scope") != TRUSTED_REPO_COMPARE_SCOPE:
        failures.append("compare_scope_mismatch")
    if payload.get("operator_surface") != OPERATOR_SURFACE:
        failures.append("operator_surface_mismatch")
    if mode == "campaign_report":
        failures.extend(_campaign_failures(payload))
    for report in reports:
        failures.extend(str(item) for item in report.get("missing_evidence") or [])
        if report.get("observed_result") != "success":
            failures.append("bundle_verification_failed")
        if report.get("side_effect_free_verification") is not True:
            failures.append("verifier_side_effect_absence_not_mechanically_proven")
    return unique(failures)


def _campaign_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if int(report.get("run_count") or 0) < 2:
        failures.append("repeat_evidence_missing")
    if int(report.get("successful_verification_count") or 0) != int(report.get("run_count") or 0):
        failures.append("bundle_verification_failed")
    for key, reason in (
        ("verdict_signature_digests", "verdict_signature_not_stable"),
        ("validator_signature_digests", "validator_signature_not_stable"),
        ("invariant_model_signature_digests", "invariant_model_signature_not_stable"),
        ("substrate_signature_digests", "substrate_signature_not_stable"),
    ):
        if len([item for item in report.get(key) or [] if item]) != 1:
            failures.append(reason)
    if report.get("must_catch_outcomes_stable") is not True:
        failures.append("must_catch_outcomes_not_stable")
    if report.get("side_effect_free_verification") is not True:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    failures.extend(str(item) for item in report.get("missing_evidence") or [])
    if report.get("observed_result") != "success" or report.get("claim_tier") != TARGET_CLAIM_TIER:
        failures.append("campaign_verdict_not_successful")
    return unique(failures)


def _claim_ladder(payload: dict[str, Any], mode: str, reports: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    report_success = any(report.get("observed_result") == "success" and not report.get("missing_evidence") for report in reports)
    campaign_success = mode == "campaign_report" and not _campaign_failures(payload)
    allowed: list[str] = []
    if report_success or campaign_success:
        allowed.append(FALLBACK_CLAIM_TIER)
    if campaign_success:
        allowed.append(TARGET_CLAIM_TIER)
    forbidden: list[dict[str, Any]] = []
    if TARGET_CLAIM_TIER not in allowed:
        forbidden.append(_forbidden(TARGET_CLAIM_TIER, ["repeat_evidence_missing"]))
    forbidden.append(_forbidden("replay_deterministic", ["replay_evidence_missing"]))
    forbidden.append(_forbidden("text_deterministic", ["text_identity_evidence_missing"]))
    return allowed, forbidden


def _transition_results(
    invariant_statuses: dict[str, str],
    payload: dict[str, Any],
    mode: str,
    reports: list[dict[str, Any]],
    allowed_claims: list[str],
) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    for name, invariant_ids in TRANSITION_INVARIANTS.items():
        failures = [item for item in invariant_ids if invariant_statuses.get(item) != "pass"]
        transitions.append(_transition(name, invariant_ids, failures))
    verifier_failures = []
    if mode == "unsupported" or not reports:
        verifier_failures.append("no_admitted_witness_report")
    if any(report.get("observed_result") != "success" for report in reports):
        verifier_failures.append("bundle_verification_failed")
    if any(report.get("side_effect_free_verification") is not True for report in reports):
        verifier_failures.append("verifier_side_effect_absence_not_mechanically_proven")
    transitions.append(_transition("verify_bundle", ("witness_report_success", "side_effect_free_verification"), verifier_failures))
    claim_failures = [] if allowed_claims else ["no_allowed_claim_tier"]
    if mode == "campaign_report" and payload.get("claim_tier") != TARGET_CLAIM_TIER:
        claim_failures.append("campaign_verdict_not_successful")
    transitions.append(_transition("assign_claim_tier", ("claim_ladder",), claim_failures))
    return transitions


def _transition(name: str, preconditions: tuple[str, ...], failures: list[str]) -> dict[str, Any]:
    return {
        "transition": name,
        "status": "pass" if not failures else "fail",
        "preconditions": list(preconditions),
        "blocking_reasons": list(failures),
    }


def _forbidden_transition_results(invariant_statuses: dict[str, str], requested_missing: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name, invariant_ids, reason in FORBIDDEN_TRANSITION_RULES:
        violated = any(invariant_statuses.get(item) != "pass" for item in invariant_ids)
        if name == "claim_upgrade_without_repeat_replay_or_text_evidence":
            violated = violated or bool(requested_missing)
        results.append({"forbidden_transition": name, "status": "blocked" if violated else "not_observed", "reason": reason if violated else ""})
    return results


def _state_results(transitions: list[dict[str, Any]], claim_status: str, mode: str) -> list[dict[str, str]]:
    transition_status = {item["transition"]: item["status"] for item in transitions}
    state_map = {
        "no_admissible_bundle": "observed" if mode == "unsupported" else "not_observed",
        "admitted_input_observed": _state_from(transition_status, "admit_run"),
        "policy_and_configuration_observed": _state_from(transition_status, "resolve_policy_and_configuration"),
        "approval_or_operator_decision_observed": _state_from(transition_status, "resolve_operator_decision"),
        "checkpoint_accepted": _state_from(transition_status, "accept_checkpoint"),
        "resource_authority_established": _state_from(transition_status, "establish_resource_authority"),
        "effect_evidence_observed": _state_from(transition_status, "publish_effect_evidence"),
        "validator_or_contract_verdict_observed": _state_from(transition_status, "publish_validator_or_contract_verdict"),
        "final_truth_observed": _state_from(transition_status, "publish_final_truth"),
        "verifier_accepted": _state_from(transition_status, "verify_bundle"),
        "verifier_rejected": "observed" if transition_status.get("verify_bundle") == "fail" else "not_observed",
        "claim_downgraded": "observed" if claim_status == "downgraded" else "not_observed",
    }
    return [{"state": name, "status": state_map[name]} for name in STATE_NAMES]


def _state_from(transitions: dict[str, str], transition: str) -> str:
    return "observed" if transitions.get(transition) == "pass" else "missing"


def _failed_transition_reasons(transitions: list[dict[str, Any]]) -> list[str]:
    return unique([str(reason) for item in transitions if item.get("status") == "fail" for reason in item.get("blocking_reasons") or []])


def _missing_proof_blockers(payload: dict[str, Any], mode: str, reports: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if mode == "campaign_report" and not payload.get("side_effect_free_verification"):
        blockers.append("verifier_side_effect_absence_not_mechanically_proven")
    for report in reports:
        if not text(report.get("invariant_model_signature_digest")):
            blockers.append("invariant_model_signature_not_stable")
        if not text(report.get("substrate_signature_digest")):
            blockers.append("substrate_signature_not_stable")
        if not text(report.get("validator_signature_digest")):
            blockers.append("validator_signature_not_stable")
    return unique(blockers)


def _normalized_evidence(
    payload: dict[str, Any],
    *,
    mode: str,
    invariant_statuses: dict[str, str],
    missing_proof_blockers: list[str],
    forbidden_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    validator = _normalized_validator_verdict(payload, mode)
    return {
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "bounded_effect_class": BOUNDED_EFFECT_CLASS,
        "bounded_artifact_path": CONFIG_ARTIFACT_PATH,
        "invariant_statuses": invariant_statuses,
        "validator_verdict": validator,
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
        "claim_tier_blockers": _claim_blockers(forbidden_claims),
        "missing_proof_blockers": list(missing_proof_blockers),
        "non_semantic_exclusions": ["recorded_at_utc", "verified_at_utc", "run_id", "session_id", "bundle_id", "input_refs", "evidence_ref", "diff_ledger"],
    }


def _normalized_validator_verdict(payload: dict[str, Any], mode: str) -> dict[str, str]:
    if mode == "bundle":
        validator = as_dict(payload.get("validator_result"))
        return {
            "schema_version": text(validator.get("schema_version")),
            "validation_result": text(validator.get("validation_result")),
            "signature_present": "yes" if text(validator.get("validator_signature_digest")) else "no",
        }
    if mode == "campaign_report":
        digests = [text(item) for item in payload.get("validator_signature_digests") or [] if text(item)]
        return {"schema_version": VALIDATOR_SCHEMA_VERSION, "validation_result": "pass" if len(digests) == 1 else "unstable", "signature_present": "yes" if digests else "no"}
    validator_digest = text(payload.get("validator_signature_digest"))
    return {"schema_version": VALIDATOR_SCHEMA_VERSION, "validation_result": "pass" if validator_digest else "missing", "signature_present": "yes" if validator_digest else "no"}


def _model_signature_material(normalized: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": FINITE_TRUST_KERNEL_MODEL_SCHEMA_VERSION,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "invariant_ids_and_statuses": normalized["invariant_statuses"],
        "must_catch_outcome_set": normalized["must_catch_outcomes"],
        "claim_tier_blockers": normalized["claim_tier_blockers"],
        "missing_proof_blockers": normalized["missing_proof_blockers"],
    }


def _invariant_mapping() -> list[dict[str, Any]]:
    return [
        {"transition": transition, "invariant_ids": list(invariant_ids)}
        for transition, invariant_ids in TRANSITION_INVARIANTS.items()
    ]


def _claim_blockers(forbidden_claims: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {text(item.get("claim_tier")): [text(reason) for reason in item.get("reason_codes") or []] for item in forbidden_claims}


def _claim_downgrade_reasons(requested_missing: list[str]) -> list[str]:
    reasons: list[str] = []
    for claim in requested_missing:
        if claim == TARGET_CLAIM_TIER:
            reasons.append("repeat_evidence_missing")
        elif claim == "replay_deterministic":
            reasons.append("replay_evidence_missing")
        elif claim == "text_deterministic":
            reasons.append("text_identity_evidence_missing")
        else:
            reasons.append("unsupported_claim_request")
    return unique(reasons)


def _failure_causes(reason_codes: list[str]) -> list[dict[str, str]]:
    return [
        {
            "reason_code": reason,
            "cause": REASON_CAUSES.get(reason, "missing_evidence"),
        }
        for reason in unique(reason_codes)
    ]


def _forbidden(claim_tier: str, reasons: list[str]) -> dict[str, Any]:
    return {"claim_tier": claim_tier, "reason_codes": unique(reasons), "missing_evidence": unique(reasons), "blocking_check_ids": unique(reasons)}


def _highest_allowed(allowed_claims: list[str]) -> str:
    ranked = [claim for claim in CLAIM_ORDER if claim in allowed_claims]
    return ranked[-1] if ranked else ""
