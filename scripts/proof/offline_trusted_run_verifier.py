from __future__ import annotations

import copy
from typing import Any

from scripts.proof.trusted_run_witness_contract import (
    BUNDLE_SCHEMA_VERSION,
    COMPARE_SCOPE,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    PROOF_RESULTS_ROOT,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    now_utc_iso,
    stable_json_digest,
    verify_witness_bundle_payload,
)

OFFLINE_VERIFIER_SCHEMA_VERSION = "offline_trusted_run_verifier.v1"
REPLAY_EVIDENCE_SCHEMA_VERSION = "offline_replay_evidence.v1"
TEXT_IDENTITY_SCHEMA_VERSION = "offline_text_identity_evidence.v1"
DEFAULT_OFFLINE_VERIFIER_OUTPUT = PROOF_RESULTS_ROOT / "offline_trusted_run_verifier.json"
CLAIM_ORDER = [
    FALLBACK_CLAIM_TIER,
    TARGET_CLAIM_TIER,
    "replay_deterministic",
    "text_deterministic",
]
SUPPORTED_INPUT_MODES = {
    "auto",
    "bundle",
    "single_report",
    "campaign_report",
    "replay_report",
    "text_identity_report",
}


def evaluate_offline_trusted_run_claim(
    payload: dict[str, Any],
    *,
    input_mode: str = "auto",
    requested_claims: list[str] | None = None,
    evidence_ref: str = "",
) -> dict[str, Any]:
    clean_payload = _without_diff_ledger(payload)
    mode = _resolve_input_mode(clean_payload, input_mode)
    requested = _valid_requested_claims(requested_claims)
    if mode == "bundle":
        report = verify_witness_bundle_payload(clean_payload, evidence_ref=evidence_ref)
        return _evaluate_single_report(
            report,
            input_mode=mode,
            requested_claims=requested,
            evidence_ref=evidence_ref,
            source_schema=str(clean_payload.get("schema_version") or ""),
        )
    if mode == "single_report":
        return _evaluate_single_report(
            clean_payload,
            input_mode=mode,
            requested_claims=requested,
            evidence_ref=evidence_ref,
            source_schema=str(clean_payload.get("schema_version") or ""),
        )
    if mode == "campaign_report":
        return _evaluate_campaign_report(
            clean_payload,
            input_mode=mode,
            requested_claims=requested,
            evidence_ref=evidence_ref,
            source_schema=str(clean_payload.get("schema_version") or ""),
        )
    if mode in {"replay_report", "text_identity_report"}:
        return _evaluate_future_claim_report(
            clean_payload,
            input_mode=mode,
            requested_claims=requested,
            evidence_ref=evidence_ref,
            source_schema=str(clean_payload.get("schema_version") or ""),
        )
    return _blocked_output(
        input_mode=mode,
        source_schema=str(clean_payload.get("schema_version") or ""),
        requested_claims=requested,
        evidence_ref=evidence_ref,
        missing_evidence=[_unsupported_reason(clean_payload, mode)],
    )


def _evaluate_future_claim_report(
    payload: dict[str, Any],
    *,
    input_mode: str,
    requested_claims: list[str],
    evidence_ref: str,
    source_schema: str,
) -> dict[str, Any]:
    if input_mode == "replay_report":
        claim = "replay_deterministic"
        expected_schema = REPLAY_EVIDENCE_SCHEMA_VERSION
        reasons = _future_replay_failures(payload, source_schema, expected_schema)
    else:
        claim = "text_deterministic"
        expected_schema = TEXT_IDENTITY_SCHEMA_VERSION
        reasons = _future_text_failures(payload, source_schema, expected_schema)
    return _build_output(
        input_mode=input_mode,
        source_schema=source_schema,
        requested_claims=requested_claims or [claim],
        evidence_ref=evidence_ref,
        record_id=str(payload.get("record_id") or ""),
        allowed_claims=[],
        forbidden_claims=[_forbidden(claim, reasons, reasons)],
        missing_evidence=reasons,
        basis_digests={},
        side_effect_free=False,
    )


def _evaluate_single_report(
    report: dict[str, Any],
    *,
    input_mode: str,
    requested_claims: list[str],
    evidence_ref: str,
    source_schema: str,
) -> dict[str, Any]:
    failures = _single_report_failures(report)
    lab_allowed = not failures
    allowed_claims = [FALLBACK_CLAIM_TIER] if lab_allowed else []
    forbidden = []
    if lab_allowed:
        forbidden.append(_forbidden(TARGET_CLAIM_TIER, ["repeat_evidence_missing"], ["repeat_evidence_missing"]))
        forbidden.extend(_future_forbidden())
    else:
        forbidden.extend(_all_claims_forbidden(failures))
    return _build_output(
        input_mode=input_mode,
        source_schema=source_schema,
        requested_claims=requested_claims,
        evidence_ref=evidence_ref,
        record_id=str(report.get("bundle_id") or report.get("record_id") or ""),
        allowed_claims=allowed_claims,
        forbidden_claims=forbidden,
        missing_evidence=failures,
        basis_digests=_single_report_basis_digests(report),
        side_effect_free=report.get("side_effect_free_verification") is True,
    )


def _evaluate_campaign_report(
    report: dict[str, Any],
    *,
    input_mode: str,
    requested_claims: list[str],
    evidence_ref: str,
    source_schema: str,
) -> dict[str, Any]:
    campaign_failures = _campaign_failures(report)
    bundle_reports = [item for item in report.get("bundle_reports") or [] if isinstance(item, dict)]
    lab_allowed = any(not _single_report_failures(item) for item in bundle_reports)
    verdict_allowed = not campaign_failures
    allowed_claims: list[str] = []
    if lab_allowed or verdict_allowed:
        allowed_claims.append(FALLBACK_CLAIM_TIER)
    if verdict_allowed:
        allowed_claims.append(TARGET_CLAIM_TIER)

    forbidden: list[dict[str, Any]] = []
    if not verdict_allowed:
        reasons = campaign_failures or ["repeat_evidence_missing"]
        forbidden.append(_forbidden(TARGET_CLAIM_TIER, reasons, reasons))
    forbidden.extend(_future_forbidden())
    if not allowed_claims:
        forbidden = _all_claims_forbidden(campaign_failures or ["bundle_verification_failed"])
    return _build_output(
        input_mode=input_mode,
        source_schema=source_schema,
        requested_claims=requested_claims,
        evidence_ref=evidence_ref,
        record_id=_campaign_record_id(report),
        allowed_claims=allowed_claims,
        forbidden_claims=forbidden,
        missing_evidence=campaign_failures,
        basis_digests=_campaign_basis_digests(report),
        side_effect_free=report.get("side_effect_free_verification") is True,
    )


def _build_output(
    *,
    input_mode: str,
    source_schema: str,
    requested_claims: list[str],
    evidence_ref: str,
    record_id: str,
    allowed_claims: list[str],
    forbidden_claims: list[dict[str, Any]],
    missing_evidence: list[str],
    basis_digests: dict[str, Any],
    side_effect_free: bool,
) -> dict[str, Any]:
    selected = _highest_allowed(allowed_claims) or FALLBACK_CLAIM_TIER
    blocked = not allowed_claims
    requested_missing = [claim for claim in requested_claims if claim not in allowed_claims]
    claim_status = "blocked" if blocked else ("downgraded" if requested_missing else "allowed")
    observed_result = "failure" if blocked else ("partial success" if requested_missing else "success")
    observed_path = "blocked" if blocked else "primary"
    checks = _checks_from_evidence(missing_evidence)
    output = {
        "schema_version": OFFLINE_VERIFIER_SCHEMA_VERSION,
        "verified_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "input_mode": input_mode,
        "source_schema_version": source_schema,
        "input_refs": [evidence_ref] if evidence_ref else [],
        "record_id": record_id,
        "observed_path": observed_path,
        "observed_result": observed_result,
        "claim_status": claim_status,
        "claim_tier": selected,
        "allowed_claims": allowed_claims,
        "forbidden_claims": forbidden_claims,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "policy_digest": str(basis_digests.get("policy_digest") or ""),
        "control_bundle_ref": str(basis_digests.get("control_bundle_ref") or ""),
        "evidence_ref": evidence_ref,
        "required_checks": checks["required"],
        "passed_checks": checks["passed"],
        "failed_checks": checks["failed"],
        "missing_evidence": _unique(missing_evidence),
        "basis_digests": basis_digests,
        "claim_ladder_basis": {
            "requested_claims": requested_claims,
            "selected_claim": selected,
            "allowed_claims": allowed_claims,
            "highest_allowed": _highest_allowed(allowed_claims),
        },
        "side_effect_free_verification": side_effect_free,
    }
    output["report_signature_digest"] = stable_json_digest(_signature_material(output))
    return output


def _blocked_output(
    *,
    input_mode: str,
    source_schema: str,
    requested_claims: list[str],
    evidence_ref: str,
    missing_evidence: list[str],
) -> dict[str, Any]:
    return _build_output(
        input_mode=input_mode,
        source_schema=source_schema,
        requested_claims=requested_claims,
        evidence_ref=evidence_ref,
        record_id="",
        allowed_claims=[],
        forbidden_claims=_all_claims_forbidden(missing_evidence),
        missing_evidence=missing_evidence,
        basis_digests={},
        side_effect_free=False,
    )


def _single_report_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        failures.append("schema_version_missing_or_unsupported")
    if report.get("compare_scope") != COMPARE_SCOPE:
        failures.append("compare_scope_mismatch")
    if report.get("operator_surface") != OPERATOR_SURFACE:
        failures.append("operator_surface_mismatch")
    if report.get("observed_result") != "success":
        failures.append("bundle_verification_failed")
    if report.get("side_effect_free_verification") is not True:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    if not _contract_digest(report):
        failures.append("contract_verdict_missing")
    if not str(report.get("invariant_model_signature_digest") or ""):
        failures.append("invariant_model_signature_not_stable")
    if not str(report.get("substrate_signature_digest") or ""):
        failures.append("substrate_signature_not_stable")
    failures.extend(str(item) for item in report.get("missing_evidence") or [])
    return _unique(failures)


def _campaign_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        failures.append("schema_version_missing_or_unsupported")
    if report.get("compare_scope") != COMPARE_SCOPE:
        failures.append("compare_scope_mismatch")
    if report.get("operator_surface") != OPERATOR_SURFACE:
        failures.append("operator_surface_mismatch")
    if int(report.get("run_count") or 0) < 2:
        failures.append("repeat_evidence_missing")
    if int(report.get("successful_verification_count") or 0) != int(report.get("run_count") or 0):
        failures.append("bundle_verification_failed")
    if len([item for item in report.get("verdict_signature_digests") or [] if item]) != 1:
        failures.append("verdict_signature_not_stable")
    if len([item for item in report.get("invariant_model_signature_digests") or [] if item]) != 1:
        failures.append("invariant_model_signature_not_stable")
    if len([item for item in report.get("substrate_signature_digests") or [] if item]) != 1:
        failures.append("substrate_signature_not_stable")
    if report.get("must_catch_outcomes_stable") is not True:
        failures.append("must_catch_outcomes_not_stable")
    if report.get("side_effect_free_verification") is not True:
        failures.append("verifier_side_effect_absence_not_mechanically_proven")
    failures.extend(str(item) for item in report.get("missing_evidence") or [])
    if report.get("observed_result") != "success" or report.get("claim_tier") != TARGET_CLAIM_TIER:
        failures.append("campaign_verdict_not_successful")
    return _unique(failures)


def _single_report_basis_digests(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_digest": str(report.get("policy_digest") or ""),
        "control_bundle_ref": str(report.get("control_bundle_ref") or ""),
        "contract_verdict_digest": _contract_digest(report),
        "invariant_model_signature_digest": str(report.get("invariant_model_signature_digest") or ""),
        "substrate_signature_digest": str(report.get("substrate_signature_digest") or ""),
        "must_catch_outcomes_digest": stable_json_digest({"must_catch_outcomes": report.get("must_catch_outcomes") or []}),
    }


def _campaign_basis_digests(report: dict[str, Any]) -> dict[str, Any]:
    bundle_reports = [item for item in report.get("bundle_reports") or [] if isinstance(item, dict)]
    policy_digests = sorted({str(item.get("policy_digest") or "") for item in bundle_reports if item.get("policy_digest")})
    return {
        "policy_digest": policy_digests[0] if len(policy_digests) == 1 else "",
        "policy_digests": policy_digests,
        "verdict_signature_digests": list(report.get("verdict_signature_digests") or []),
        "invariant_model_signature_digests": list(report.get("invariant_model_signature_digests") or []),
        "substrate_signature_digests": list(report.get("substrate_signature_digests") or []),
        "must_catch_outcomes_digest": stable_json_digest({"must_catch_outcomes": report.get("must_catch_outcomes") or []}),
    }


def _contract_digest(report: dict[str, Any]) -> str:
    verdict = report.get("contract_verdict")
    return str(verdict.get("verdict_signature_digest") or "") if isinstance(verdict, dict) else ""


def _future_forbidden() -> list[dict[str, Any]]:
    return [
        _forbidden("replay_deterministic", ["replay_evidence_missing"], ["replay_evidence_missing"]),
        _forbidden("text_deterministic", ["text_identity_evidence_missing"], ["text_identity_evidence_missing"]),
    ]


def _future_replay_failures(payload: dict[str, Any], source_schema: str, expected_schema: str) -> list[str]:
    if source_schema != expected_schema:
        return ["replay_evidence_missing"]
    if payload.get("compare_scope") != COMPARE_SCOPE:
        return ["replay_compare_scope_mismatch"]
    if payload.get("replay_result") != "success":
        return ["replay_result_not_stable"]
    return ["replay_evidence_missing"]


def _future_text_failures(payload: dict[str, Any], source_schema: str, expected_schema: str) -> list[str]:
    if source_schema != expected_schema:
        return ["text_identity_evidence_missing"]
    if payload.get("compare_scope") != COMPARE_SCOPE:
        return ["text_compare_scope_mismatch"]
    if payload.get("output_hash_stable") is not True and payload.get("byte_identity_stable") is not True:
        return ["text_hash_not_stable"]
    return ["text_identity_evidence_missing"]


def _all_claims_forbidden(reasons: list[str]) -> list[dict[str, Any]]:
    return [_forbidden(claim, reasons, reasons) for claim in CLAIM_ORDER]


def _forbidden(claim: str, reason_codes: list[str], missing_evidence: list[str]) -> dict[str, Any]:
    reasons = _unique(reason_codes)
    return {
        "claim_tier": claim,
        "reason_codes": reasons,
        "missing_evidence": _unique(missing_evidence),
        "blocking_check_ids": reasons,
    }


def _checks_from_evidence(missing_evidence: list[str]) -> dict[str, list[dict[str, str]]]:
    required = [{"id": "offline_claim_ladder", "status": "required"}]
    if not missing_evidence:
        return {"required": required, "passed": [{"id": "offline_claim_ladder", "status": "pass"}], "failed": []}
    failed = [{"id": item, "status": "fail", "reason": item} for item in _unique(missing_evidence)]
    return {"required": required, "passed": [], "failed": failed}


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


def _unsupported_reason(payload: dict[str, Any], input_mode: str) -> str:
    if input_mode == "unsupported" or payload.get("schema_version") not in {BUNDLE_SCHEMA_VERSION, REPORT_SCHEMA_VERSION}:
        return "schema_version_missing_or_unsupported"
    return f"{input_mode}_schema_not_supported"


def _valid_requested_claims(requested_claims: list[str] | None) -> list[str]:
    return [claim for claim in requested_claims or [] if claim in CLAIM_ORDER]


def _highest_allowed(allowed_claims: list[str]) -> str:
    ranked = [claim for claim in CLAIM_ORDER if claim in allowed_claims]
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


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
