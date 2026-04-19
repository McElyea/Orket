from __future__ import annotations

import copy
from typing import Any

from scripts.proof.trusted_terraform_plan_decision_contract import (
    CONTRACT_VERDICT_SCHEMA_VERSION,
    FALLBACK_CLAIM_TIER,
    MUST_CATCH_OUTCOMES,
    OPERATOR_SURFACE,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
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
    compare_scope=TRUSTED_TERRAFORM_COMPARE_SCOPE,
    operator_surface=OPERATOR_SURFACE,
    fallback_claim_tier=FALLBACK_CLAIM_TIER,
    target_claim_tier=TARGET_CLAIM_TIER,
    bundle_schema_version="trusted_run.witness_bundle.v1",
    report_schema_version=REPORT_SCHEMA_VERSION,
)


def evaluate_trusted_terraform_plan_decision_invariants(bundle: dict[str, Any]) -> dict[str, Any]:
    authority = _as_dict(bundle.get("authority_lineage"))
    observed = _as_dict(bundle.get("observed_effect"))
    validator = _as_dict(bundle.get("validator_result"))
    run_id = _text(bundle.get("run_id"))
    session_id = _text(bundle.get("session_id"))
    failures: list[str] = []
    checks: list[dict[str, str]] = []

    def check(check_id: str, passed: bool, failure: str, basis: str) -> None:
        checks.append({"id": check_id, "status": "pass" if passed else "fail", "failure": "" if passed else failure, "basis": basis})
        if not passed:
            _append_unique(failures, failure)

    check("TTPD-INV-001", bundle.get("schema_version") == "trusted_run.witness_bundle.v1", "schema_version_missing_or_unsupported", "bundle schema")
    check("TTPD-INV-002", bundle.get("compare_scope") == TRUSTED_TERRAFORM_COMPARE_SCOPE, "compare_scope_missing_or_unsupported", "compare scope")
    check("TTPD-INV-003", bundle.get("operator_surface") == OPERATOR_SURFACE, "operator_surface_missing", "operator surface")
    check("TTPD-INV-004", session_id in run_id and run_id.startswith("trusted-terraform-run:"), "canonical_run_id_drift", "canonical run id")
    check("TTPD-INV-005", _policy_configuration_ok(bundle), "policy_or_configuration_missing", "policy and configuration")
    check("TTPD-INV-006", _governed_input_ok(authority), "governed_input_missing", "governed input")
    check("TTPD-INV-007", validator.get("schema_version") == VALIDATOR_SCHEMA_VERSION, "missing_validator_result", "validator presence")
    check("TTPD-INV-008", validator.get("validation_result") == "pass", "validator_failed", "validator pass")
    check("TTPD-INV-009", observed.get("output_exists") is True and bool(_text(observed.get("actual_output_artifact_path"))), "risk_verdict_drift", "review artifact")
    check("TTPD-INV-010", observed.get("deterministic_analysis_complete") is True, "publish_without_complete_analysis", "deterministic analysis")
    check("TTPD-INV-011", observed.get("publish_decision") in {"normal_publish", "degraded_publish"}, "publish_without_complete_analysis", "publish decision")
    check("TTPD-INV-012", observed.get("audit_publication_present") is True and _audit_ok(authority), "audit_publication_without_publish", "audit evidence")
    check("TTPD-INV-013", not observed.get("forbidden_mutations"), "undeclared_durable_mutation", "mutation boundary")
    check("TTPD-INV-014", _final_truth_success_ok(authority), "missing_final_truth", "final truth")
    check("TTPD-INV-015", bundle.get("claim_tier") == FALLBACK_CLAIM_TIER, "single_bundle_claim_tier_must_be_lab_only", "single bundle claim")
    check("TTPD-INV-016", bundle.get("claim_tier") != "replay_deterministic", "replay_evidence_missing", "replay guard")
    check("TTPD-INV-017", bundle.get("claim_tier") != "text_deterministic", "text_identity_evidence_missing", "text guard")

    return {
        "schema_version": INVARIANT_MODEL_SCHEMA_VERSION,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "result": "pass" if not failures else "fail",
        "checked_invariants": checks,
        "failures": failures,
        "missing_proof_blockers": [],
        "transition_trace": _transition_trace(checks),
        "invariant_signature_digest": stable_json_digest(_signature_material(INVARIANT_MODEL_SCHEMA_VERSION, checks, failures)),
    }


def evaluate_trusted_terraform_plan_decision_substrate(bundle: dict[str, Any]) -> dict[str, Any]:
    authority = _as_dict(bundle.get("authority_lineage"))
    validator = _as_dict(bundle.get("validator_result"))
    rows: list[dict[str, str]] = []
    failures: list[str] = []

    def row(family: str, classification: str, passed: bool, failure: str, question: str) -> None:
        rows.append({"record_family": family, "classification": classification, "status": "pass" if passed else "fail", "failure": "" if passed else failure, "verifier_question": question})
        if not passed:
            _append_unique(failures, failure)

    row("governed_input", "required_authority", _governed_input_ok(authority), "governed_input_missing", "What plan decision was requested?")
    row("policy_snapshot", "required_authority", _policy_configuration_ok(bundle), "policy_or_configuration_missing", "What policy admitted the run?")
    row("configuration_snapshot", "required_authority", bool(_text(bundle.get("configuration_snapshot_ref"))), "policy_or_configuration_missing", "Which config snapshot applied?")
    row("run", "required_authority", _run_ok(authority), "canonical_run_id_drift", "Which run is canonical?")
    row("step", "required_authority", _step_ok(authority), "canonical_run_id_drift", "Which step published the decision?")
    row("review_decision", "required_authority", _review_decision_ok(authority), "risk_verdict_drift", "What decision was published?")
    row("audit_publication", "required_authority", _audit_ok(authority), "audit_publication_without_publish", "Was the audit publication emitted?")
    row("effect_journal", "required_authority", _effect_journal_ok(authority), "missing_effect_evidence", "What effect occurred?")
    row("validator_result", "required_authority", validator.get("validation_result") == "pass", "validator_failed", "Did deterministic validation pass?")
    row("final_truth", "required_authority", _final_truth_success_ok(authority), "missing_final_truth", "What terminal truth was assigned?")
    row("run_summary", "projection_only", True, "", "Where are support artifacts?")
    row("human_summary", "projection_only", True, "", "What should a human inspect?")

    return {
        "schema_version": SUBSTRATE_SCHEMA_VERSION,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "result": "pass" if not failures else "fail",
        "record_families": rows,
        "failures": failures,
        "missing_substrate_blockers": [],
        "substrate_signature_digest": stable_json_digest(_signature_material(SUBSTRATE_SCHEMA_VERSION, rows, failures)),
    }


def verify_trusted_terraform_plan_decision_bundle_payload(bundle: dict[str, Any], *, evidence_ref: str = "") -> dict[str, Any]:
    from scripts.proof.trusted_run_proof_foundation import evaluate_offline_verifier_non_interference

    clean = _without_diff_ledger(bundle)
    included_verdict = _as_dict(clean.get("contract_verdict"))
    recomputed = build_contract_verdict(clean)
    invariant_model = evaluate_trusted_terraform_plan_decision_invariants(clean)
    substrate_model = evaluate_trusted_terraform_plan_decision_substrate(clean)
    non_interference = evaluate_offline_verifier_non_interference()
    validator = _as_dict(clean.get("validator_result"))
    failures = build_bundle_verification_failures(
        included_verdict,
        recomputed,
        invariant_model,
        substrate_model,
        side_effect_free=non_interference.get("result") == "pass",
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary" if clean.get("schema_version") == "trusted_run.witness_bundle.v1" else "blocked",
        "observed_result": "success" if not failures else "failure",
        "claim_tier": FALLBACK_CLAIM_TIER,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
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
        "offline_verifier_non_interference_signature_digest": _text(non_interference.get("non_interference_signature_digest")),
        "validator_signature_digest": _text(validator.get("validator_signature_digest")),
        "included_contract_verdict_digest": _text(included_verdict.get("verdict_signature_digest")),
        "recomputed_contract_verdict_digest": _text(recomputed.get("verdict_signature_digest")),
        "invariant_model_signature_digest": _text(invariant_model.get("invariant_signature_digest")),
        "substrate_signature_digest": _text(substrate_model.get("substrate_signature_digest")),
        "missing_evidence": failures,
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
    }


def build_trusted_terraform_plan_decision_campaign_report(
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
        "admit_run": ("TTPD-INV-004", "TTPD-INV-005", "TTPD-INV-006"),
        "validate_decision": ("TTPD-INV-007", "TTPD-INV-008", "TTPD-INV-009", "TTPD-INV-010"),
        "publish_decision": ("TTPD-INV-011", "TTPD-INV-012", "TTPD-INV-013"),
        "publish_final_truth": ("TTPD-INV-014",),
        "verify_bundle": ("TTPD-INV-015", "TTPD-INV-016", "TTPD-INV-017"),
    }
    statuses = {item["id"]: item["status"] for item in checks}
    return [{"transition": name, "status": "pass" if all(statuses.get(item) == "pass" for item in ids) else "fail"} for name, ids in groups.items()]


def _signature_material(schema: str, checks: list[dict[str, Any]], failures: list[str]) -> dict[str, Any]:
    key = "invariants" if schema == INVARIANT_MODEL_SCHEMA_VERSION else "families"
    items = {str(item.get("id") or item.get("record_family")): str(item["status"]) for item in checks}
    return {
        "schema_version": schema,
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        key: items,
        "failures": sorted(failures),
    }


def _policy_configuration_ok(bundle: dict[str, Any]) -> bool:
    return all(bool(_text(bundle.get(key))) for key in ("policy_digest", "policy_snapshot_ref", "configuration_snapshot_ref", "control_bundle_ref"))


def _governed_input_ok(authority: dict[str, Any]) -> bool:
    governed_input = _as_dict(authority.get("governed_input"))
    return bool(_text(governed_input.get("plan_s3_uri"))) and isinstance(governed_input.get("forbidden_operations"), list)


def _run_ok(authority: dict[str, Any]) -> bool:
    run = _as_dict(authority.get("run"))
    return bool(_text(run.get("run_id"))) and bool(_text(run.get("current_attempt_id")))


def _step_ok(authority: dict[str, Any]) -> bool:
    step = _as_dict(authority.get("step"))
    return bool(_text(step.get("latest_step_id")))


def _review_decision_ok(authority: dict[str, Any]) -> bool:
    review = _as_dict(authority.get("review_decision"))
    return _text(review.get("risk_verdict")) in {"safe_for_v1_policy", "risky_for_v1_policy"} and _text(review.get("publish_decision")) in {"normal_publish", "degraded_publish"}


def _audit_ok(authority: dict[str, Any]) -> bool:
    audit = _as_dict(authority.get("audit_publication"))
    return bool(_text(audit.get("publication_id"))) and bool(_text(audit.get("audit_item_digest")))


def _effect_journal_ok(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    return int(journal.get("effect_entry_count") or 0) >= 1 and bool(_text(journal.get("latest_observed_result_ref")))


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
