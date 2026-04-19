from __future__ import annotations

import copy
from typing import Any, Callable

from scripts.proof.offline_trusted_run_verifier import (
    CLAIM_ORDER,
    OFFLINE_VERIFIER_SCHEMA_VERSION,
    REPLAY_EVIDENCE_SCHEMA_VERSION,
    TEXT_IDENTITY_SCHEMA_VERSION,
)
from scripts.proof.trusted_run_witness_contract import now_utc_iso, stable_json_digest
from scripts.proof.trusted_scope_family_common import (
    all_claims_forbidden,
    forbidden_claim,
    highest_allowed_claim,
    text,
    unique,
    without_diff_ledger,
)


def evaluate_validator_backed_scope_offline_claim(
    payload: dict[str, Any],
    *,
    config: Any,
    verify_bundle_payload: Callable[[dict[str, Any]], dict[str, Any]],
    input_mode: str = "auto",
    requested_claims: list[str] | None = None,
    evidence_ref: str = "",
) -> dict[str, Any]:
    clean = without_diff_ledger(payload)
    mode = _resolve_input_mode(clean, input_mode, config=config)
    requested = [claim for claim in requested_claims or [] if claim in CLAIM_ORDER]
    if mode == "bundle":
        report = verify_bundle_payload(clean, evidence_ref=evidence_ref)
        return _evaluate_single_report(report, mode, requested, evidence_ref, text(clean.get("schema_version")), config=config)
    if mode == "single_report":
        return _evaluate_single_report(clean, mode, requested, evidence_ref, text(clean.get("schema_version")), config=config)
    if mode == "campaign_report":
        return _evaluate_campaign_report(clean, mode, requested, evidence_ref, text(clean.get("schema_version")), config=config)
    if mode in {"replay_report", "text_identity_report"}:
        return _evaluate_future_claim(clean, mode, requested, evidence_ref, text(clean.get("schema_version")), config=config)
    return _build_output(
        input_mode=mode,
        source_schema=text(clean.get("schema_version")),
        requested=requested,
        evidence_ref=evidence_ref,
        record_id="",
        allowed=[],
        forbidden=all_claims_forbidden(["schema_version_missing_or_unsupported"]),
        missing=["schema_version_missing_or_unsupported"],
        basis={},
        side_effect_free=False,
        config=config,
    )


def _evaluate_single_report(
    report: dict[str, Any],
    mode: str,
    requested: list[str],
    evidence_ref: str,
    source_schema: str,
    *,
    config: Any,
) -> dict[str, Any]:
    failures = _single_report_failures(report, config=config)
    allowed = [config.fallback_claim_tier] if not failures else []
    forbidden = (
        [forbidden_claim(config.target_claim_tier, ["repeat_evidence_missing"])] + _future_forbidden()
        if allowed
        else all_claims_forbidden(failures)
    )
    return _build_output(
        input_mode=mode,
        source_schema=source_schema,
        requested=requested,
        evidence_ref=evidence_ref,
        record_id=text(report.get("bundle_id")),
        allowed=allowed,
        forbidden=forbidden,
        missing=failures,
        basis=_single_basis(report),
        side_effect_free=report.get("side_effect_free_verification") is True,
        config=config,
    )


def _evaluate_campaign_report(
    report: dict[str, Any],
    mode: str,
    requested: list[str],
    evidence_ref: str,
    source_schema: str,
    *,
    config: Any,
) -> dict[str, Any]:
    failures = _campaign_report_failures(report, config=config)
    bundle_reports = [item for item in report.get("bundle_reports") or [] if isinstance(item, dict)]
    lab_allowed = any(not _single_report_failures(item, config=config) for item in bundle_reports)
    verdict_allowed = not failures
    allowed: list[str] = []
    if lab_allowed or verdict_allowed:
        allowed.append(config.fallback_claim_tier)
    if verdict_allowed:
        allowed.append(config.target_claim_tier)
    forbidden = [] if verdict_allowed else [forbidden_claim(config.target_claim_tier, failures or ["repeat_evidence_missing"])]
    forbidden.extend(_future_forbidden())
    if not allowed:
        forbidden = all_claims_forbidden(failures or ["bundle_verification_failed"])
    return _build_output(
        input_mode=mode,
        source_schema=source_schema,
        requested=requested,
        evidence_ref=evidence_ref,
        record_id=_campaign_record_id(report),
        allowed=allowed,
        forbidden=forbidden,
        missing=failures,
        basis=_campaign_basis(report),
        side_effect_free=report.get("side_effect_free_verification") is True,
        config=config,
    )


def _evaluate_future_claim(
    payload: dict[str, Any],
    mode: str,
    requested: list[str],
    evidence_ref: str,
    source_schema: str,
    *,
    config: Any,
) -> dict[str, Any]:
    if mode == "replay_report":
        claim = "replay_deterministic"
        reasons = ["replay_evidence_missing"] if source_schema != REPLAY_EVIDENCE_SCHEMA_VERSION else _future_scope_failures(payload, "replay", config=config)
    else:
        claim = "text_deterministic"
        reasons = ["text_identity_evidence_missing"] if source_schema != TEXT_IDENTITY_SCHEMA_VERSION else _future_scope_failures(payload, "text", config=config)
    return _build_output(
        input_mode=mode,
        source_schema=source_schema,
        requested=requested or [claim],
        evidence_ref=evidence_ref,
        record_id=text(payload.get("record_id")),
        allowed=[],
        forbidden=[forbidden_claim(claim, reasons)],
        missing=reasons,
        basis={},
        side_effect_free=False,
        config=config,
    )


def _build_output(
    *,
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
    config: Any,
) -> dict[str, Any]:
    selected = highest_allowed_claim(allowed) or config.fallback_claim_tier
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
        "compare_scope": config.compare_scope,
        "operator_surface": config.operator_surface,
        "policy_digest": text(basis.get("policy_digest")),
        "control_bundle_ref": text(basis.get("control_bundle_ref")),
        "evidence_ref": evidence_ref,
        "required_checks": [{"id": "offline_claim_ladder", "status": "required"}],
        "passed_checks": [] if missing else [{"id": "offline_claim_ladder", "status": "pass"}],
        "failed_checks": [{"id": item, "status": "fail", "reason": item} for item in unique(missing)],
        "missing_evidence": unique(missing),
        "basis_digests": basis,
        "claim_ladder_basis": {
            "requested_claims": requested,
            "selected_claim": selected,
            "allowed_claims": allowed,
            "highest_allowed": highest_allowed_claim(allowed),
        },
        "side_effect_free_verification": side_effect_free,
    }
    output["report_signature_digest"] = stable_json_digest(_signature_material(output))
    return output


def _single_report_failures(report: dict[str, Any], *, config: Any) -> list[str]:
    failures: list[str] = []
    if report.get("schema_version") != config.report_schema_version:
        failures.append("schema_version_missing_or_unsupported")
    if report.get("compare_scope") != config.compare_scope:
        failures.append("compare_scope_mismatch")
    if report.get("operator_surface") != config.operator_surface:
        failures.append("operator_surface_mismatch")
    if report.get("observed_result") != "success":
        failures.append("bundle_verification_failed")
    if report.get("side_effect_free_verification") is not True:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    for key, reason in (
        ("validator_signature_digest", "validator_signature_not_stable"),
        ("invariant_model_signature_digest", "invariant_model_signature_not_stable"),
        ("substrate_signature_digest", "substrate_signature_not_stable"),
    ):
        if not text(report.get(key)):
            failures.append(reason)
    failures.extend(str(item) for item in report.get("missing_evidence") or [])
    return unique(failures)


def _campaign_report_failures(report: dict[str, Any], *, config: Any) -> list[str]:
    failures: list[str] = []
    if report.get("schema_version") != config.report_schema_version:
        failures.append("schema_version_missing_or_unsupported")
    if report.get("compare_scope") != config.compare_scope:
        failures.append("compare_scope_mismatch")
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
    if report.get("observed_result") != "success" or report.get("claim_tier") != config.target_claim_tier:
        failures.append("campaign_verdict_not_successful")
    return unique(failures)


def _single_basis(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_digest": text(report.get("policy_digest")),
        "control_bundle_ref": text(report.get("control_bundle_ref")),
        "validator_signature_digest": text(report.get("validator_signature_digest")),
        "invariant_model_signature_digest": text(report.get("invariant_model_signature_digest")),
        "substrate_signature_digest": text(report.get("substrate_signature_digest")),
    }


def _campaign_basis(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict_signature_digests": list(report.get("verdict_signature_digests") or []),
        "validator_signature_digests": list(report.get("validator_signature_digests") or []),
        "invariant_model_signature_digests": list(report.get("invariant_model_signature_digests") or []),
        "substrate_signature_digests": list(report.get("substrate_signature_digests") or []),
    }


def _resolve_input_mode(payload: dict[str, Any], input_mode: str, *, config: Any) -> str:
    if input_mode not in {"auto", "bundle", "single_report", "campaign_report", "replay_report", "text_identity_report"}:
        return "unsupported"
    if input_mode != "auto":
        return input_mode
    schema = payload.get("schema_version")
    if schema == config.bundle_schema_version:
        return "bundle"
    if schema == config.report_schema_version and ("run_count" in payload or "bundle_reports" in payload):
        return "campaign_report"
    if schema == config.report_schema_version:
        return "single_report"
    return "unsupported"


def _future_scope_failures(payload: dict[str, Any], family: str, *, config: Any) -> list[str]:
    if payload.get("compare_scope") != config.compare_scope:
        return [f"{family}_compare_scope_mismatch"]
    return [f"{family}_evidence_missing" if family == "replay" else "text_identity_evidence_missing"]


def _future_forbidden() -> list[dict[str, Any]]:
    return [
        forbidden_claim("replay_deterministic", ["replay_evidence_missing"]),
        forbidden_claim("text_deterministic", ["text_identity_evidence_missing"]),
    ]


def _campaign_record_id(report: dict[str, Any]) -> str:
    return f"campaign:{report.get('compare_scope') or ''}:runs:{report.get('run_count') or 0}"


def _signature_material(output: dict[str, Any]) -> dict[str, Any]:
    material = copy.deepcopy(output)
    for key in ("verified_at_utc", "record_id", "input_refs", "evidence_ref", "report_signature_digest"):
        material.pop(key, None)
    return material
