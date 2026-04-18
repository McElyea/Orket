from __future__ import annotations

import copy
from typing import Any

from scripts.proof.offline_trusted_run_verifier import (
    CLAIM_ORDER,
    OFFLINE_VERIFIER_SCHEMA_VERSION,
    REPLAY_EVIDENCE_SCHEMA_VERSION,
    TEXT_IDENTITY_SCHEMA_VERSION,
)
from scripts.proof.trusted_repo_change_contract import (
    BUNDLE_SCHEMA_VERSION,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    TRUSTED_REPO_COMPARE_SCOPE,
    now_utc_iso,
    stable_json_digest,
)
from scripts.proof.trusted_repo_change_verifier import verify_trusted_repo_change_bundle_payload

SUPPORTED_INPUT_MODES = {"auto", "bundle", "single_report", "campaign_report", "replay_report", "text_identity_report"}


def evaluate_trusted_repo_change_offline_claim(
    payload: dict[str, Any],
    *,
    input_mode: str = "auto",
    requested_claims: list[str] | None = None,
    evidence_ref: str = "",
) -> dict[str, Any]:
    clean = _without_diff_ledger(payload)
    mode = _resolve_input_mode(clean, input_mode)
    requested = [claim for claim in requested_claims or [] if claim in CLAIM_ORDER]
    if mode == "bundle":
        report = verify_trusted_repo_change_bundle_payload(clean, evidence_ref=evidence_ref)
        return _evaluate_single_report(report, mode, requested, evidence_ref, _text(clean.get("schema_version")))
    if mode == "single_report":
        return _evaluate_single_report(clean, mode, requested, evidence_ref, _text(clean.get("schema_version")))
    if mode == "campaign_report":
        return _evaluate_campaign_report(clean, mode, requested, evidence_ref, _text(clean.get("schema_version")))
    if mode in {"replay_report", "text_identity_report"}:
        return _evaluate_future_claim(clean, mode, requested, evidence_ref, _text(clean.get("schema_version")))
    return _build_output(mode, _text(clean.get("schema_version")), requested, evidence_ref, "", [], _all_claims_forbidden(["schema_version_missing_or_unsupported"]), ["schema_version_missing_or_unsupported"], {}, False)


def _evaluate_single_report(report: dict[str, Any], mode: str, requested: list[str], evidence_ref: str, source_schema: str) -> dict[str, Any]:
    failures = _single_report_failures(report)
    allowed = [FALLBACK_CLAIM_TIER] if not failures else []
    forbidden = [_forbidden(TARGET_CLAIM_TIER, ["repeat_evidence_missing"])] + _future_forbidden() if allowed else _all_claims_forbidden(failures)
    return _build_output(mode, source_schema, requested, evidence_ref, _text(report.get("bundle_id")), allowed, forbidden, failures, _single_basis(report), report.get("side_effect_free_verification") is True)


def _evaluate_campaign_report(report: dict[str, Any], mode: str, requested: list[str], evidence_ref: str, source_schema: str) -> dict[str, Any]:
    failures = _campaign_failures(report)
    bundle_reports = [item for item in report.get("bundle_reports") or [] if isinstance(item, dict)]
    lab_allowed = any(not _single_report_failures(item) for item in bundle_reports)
    verdict_allowed = not failures
    allowed: list[str] = []
    if lab_allowed or verdict_allowed:
        allowed.append(FALLBACK_CLAIM_TIER)
    if verdict_allowed:
        allowed.append(TARGET_CLAIM_TIER)
    forbidden = [] if verdict_allowed else [_forbidden(TARGET_CLAIM_TIER, failures or ["repeat_evidence_missing"])]
    forbidden.extend(_future_forbidden())
    if not allowed:
        forbidden = _all_claims_forbidden(failures or ["bundle_verification_failed"])
    return _build_output(mode, source_schema, requested, evidence_ref, _campaign_record_id(report), allowed, forbidden, failures, _campaign_basis(report), report.get("side_effect_free_verification") is True)


def _evaluate_future_claim(payload: dict[str, Any], mode: str, requested: list[str], evidence_ref: str, source_schema: str) -> dict[str, Any]:
    if mode == "replay_report":
        claim = "replay_deterministic"
        reasons = ["replay_evidence_missing"] if source_schema != REPLAY_EVIDENCE_SCHEMA_VERSION else _future_scope_failures(payload, "replay")
    else:
        claim = "text_deterministic"
        reasons = ["text_identity_evidence_missing"] if source_schema != TEXT_IDENTITY_SCHEMA_VERSION else _future_scope_failures(payload, "text")
    return _build_output(mode, source_schema, requested or [claim], evidence_ref, _text(payload.get("record_id")), [], [_forbidden(claim, reasons)], reasons, {}, False)


def _build_output(
    input_mode: str,
    source_schema: str,
    requested: list[str],
    evidence_ref: str,
    record_id: str,
    allowed: list[str],
    forbidden: list[dict[str, Any]],
    missing: list[str],
    basis: dict[str, Any],
    side_effect_free: bool,
) -> dict[str, Any]:
    selected = _highest_allowed(allowed) or FALLBACK_CLAIM_TIER
    requested_missing = [claim for claim in requested if claim not in allowed]
    status = "blocked" if not allowed else ("downgraded" if requested_missing else "allowed")
    output = {
        "schema_version": OFFLINE_VERIFIER_SCHEMA_VERSION,
        "verified_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "input_mode": input_mode,
        "source_schema_version": source_schema,
        "input_refs": [evidence_ref] if evidence_ref else [],
        "record_id": record_id,
        "observed_path": "blocked" if not allowed else "primary",
        "observed_result": "failure" if not allowed else ("partial success" if requested_missing else "success"),
        "claim_status": status,
        "claim_tier": selected,
        "allowed_claims": allowed,
        "forbidden_claims": forbidden,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "policy_digest": _text(basis.get("policy_digest")),
        "control_bundle_ref": _text(basis.get("control_bundle_ref")),
        "evidence_ref": evidence_ref,
        "required_checks": [{"id": "offline_claim_ladder", "status": "required"}],
        "passed_checks": [] if missing else [{"id": "offline_claim_ladder", "status": "pass"}],
        "failed_checks": [{"id": item, "status": "fail", "reason": item} for item in _unique(missing)],
        "missing_evidence": _unique(missing),
        "basis_digests": basis,
        "claim_ladder_basis": {"requested_claims": requested, "selected_claim": selected, "allowed_claims": allowed, "highest_allowed": _highest_allowed(allowed)},
        "side_effect_free_verification": side_effect_free,
    }
    output["report_signature_digest"] = stable_json_digest(_signature_material(output))
    return output


def _single_report_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        failures.append("schema_version_missing_or_unsupported")
    if report.get("compare_scope") != TRUSTED_REPO_COMPARE_SCOPE:
        failures.append("compare_scope_mismatch")
    if report.get("operator_surface") != OPERATOR_SURFACE:
        failures.append("operator_surface_mismatch")
    if report.get("observed_result") != "success":
        failures.append("bundle_verification_failed")
    if report.get("side_effect_free_verification") is not True:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    for key, reason in (("validator_signature_digest", "validator_signature_not_stable"), ("invariant_model_signature_digest", "invariant_model_signature_not_stable"), ("substrate_signature_digest", "substrate_signature_not_stable")):
        if not _text(report.get(key)):
            failures.append(reason)
    failures.extend(str(item) for item in report.get("missing_evidence") or [])
    return _unique(failures)


def _campaign_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        failures.append("schema_version_missing_or_unsupported")
    if report.get("compare_scope") != TRUSTED_REPO_COMPARE_SCOPE:
        failures.append("compare_scope_mismatch")
    if int(report.get("run_count") or 0) < 2:
        failures.append("repeat_evidence_missing")
    if int(report.get("successful_verification_count") or 0) != int(report.get("run_count") or 0):
        failures.append("bundle_verification_failed")
    for key, reason in (("verdict_signature_digests", "verdict_signature_not_stable"), ("validator_signature_digests", "validator_signature_not_stable"), ("invariant_model_signature_digests", "invariant_model_signature_not_stable"), ("substrate_signature_digests", "substrate_signature_not_stable")):
        if len([item for item in report.get(key) or [] if item]) != 1:
            failures.append(reason)
    if report.get("must_catch_outcomes_stable") is not True:
        failures.append("must_catch_outcomes_not_stable")
    if report.get("side_effect_free_verification") is not True:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    failures.extend(str(item) for item in report.get("missing_evidence") or [])
    if report.get("observed_result") != "success" or report.get("claim_tier") != TARGET_CLAIM_TIER:
        failures.append("campaign_verdict_not_successful")
    return _unique(failures)


def _single_basis(report: dict[str, Any]) -> dict[str, Any]:
    return {"policy_digest": _text(report.get("policy_digest")), "control_bundle_ref": _text(report.get("control_bundle_ref")), "validator_signature_digest": _text(report.get("validator_signature_digest")), "invariant_model_signature_digest": _text(report.get("invariant_model_signature_digest")), "substrate_signature_digest": _text(report.get("substrate_signature_digest"))}


def _campaign_basis(report: dict[str, Any]) -> dict[str, Any]:
    return {"verdict_signature_digests": list(report.get("verdict_signature_digests") or []), "validator_signature_digests": list(report.get("validator_signature_digests") or []), "invariant_model_signature_digests": list(report.get("invariant_model_signature_digests") or []), "substrate_signature_digests": list(report.get("substrate_signature_digests") or [])}


def _resolve_input_mode(payload: dict[str, Any], input_mode: str) -> str:
    if input_mode not in SUPPORTED_INPUT_MODES:
        return "unsupported"
    if input_mode != "auto":
        return input_mode
    schema = payload.get("schema_version")
    if schema == BUNDLE_SCHEMA_VERSION:
        return "bundle"
    if schema == REPORT_SCHEMA_VERSION and ("run_count" in payload or "bundle_reports" in payload):
        return "campaign_report"
    if schema == REPORT_SCHEMA_VERSION:
        return "single_report"
    return "unsupported"


def _future_scope_failures(payload: dict[str, Any], family: str) -> list[str]:
    if payload.get("compare_scope") != TRUSTED_REPO_COMPARE_SCOPE:
        return [f"{family}_compare_scope_mismatch"]
    return [f"{family}_evidence_missing" if family == "replay" else "text_identity_evidence_missing"]


def _future_forbidden() -> list[dict[str, Any]]:
    return [_forbidden("replay_deterministic", ["replay_evidence_missing"]), _forbidden("text_deterministic", ["text_identity_evidence_missing"])]


def _all_claims_forbidden(reasons: list[str]) -> list[dict[str, Any]]:
    return [_forbidden(claim, reasons) for claim in CLAIM_ORDER]


def _forbidden(claim: str, reasons: list[str]) -> dict[str, Any]:
    unique = _unique(reasons)
    return {"claim_tier": claim, "reason_codes": unique, "missing_evidence": unique, "blocking_check_ids": unique}


def _highest_allowed(allowed: list[str]) -> str:
    ranked = [claim for claim in CLAIM_ORDER if claim in allowed]
    return ranked[-1] if ranked else ""


def _campaign_record_id(report: dict[str, Any]) -> str:
    return f"campaign:{report.get('compare_scope') or ''}:runs:{report.get('run_count') or 0}"


def _signature_material(output: dict[str, Any]) -> dict[str, Any]:
    material = copy.deepcopy(output)
    for key in ("verified_at_utc", "record_id", "input_refs", "evidence_ref", "report_signature_digest"):
        material.pop(key, None)
    return material


def _without_diff_ledger(value: Any) -> dict[str, Any]:
    copied = copy.deepcopy(value)
    if isinstance(copied, dict):
        copied.pop("diff_ledger", None)
        return copied
    return {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
