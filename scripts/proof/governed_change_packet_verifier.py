from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from scripts.proof.governed_change_packet_contract import (
    ENTRY_PROJECTION_CLASSIFICATION,
    GOVERNED_CHANGE_PACKET_FAMILY,
    GOVERNED_CHANGE_PACKET_SCHEMA_VERSION,
    GOVERNED_CHANGE_PACKET_VERIFIER_SCHEMA_VERSION,
    PRIMARY_AUTHORITY_CLASSIFICATIONS,
    REQUIRED_PACKET_ARTIFACT_ROLES,
    json_file_digest,
    load_json_object,
    packet_verifier_signature_material,
    resolve_repo_path,
    stable_signature_digest,
)
from scripts.proof.governed_change_packet_trusted_kernel import evaluate_governed_change_packet_kernel_conformance
from scripts.proof.trusted_repo_change_contract import OPERATOR_SURFACE, TARGET_CLAIM_TIER, TRUSTED_REPO_COMPARE_SCOPE, now_utc_iso
from scripts.proof.trusted_repo_change_offline import evaluate_trusted_repo_change_offline_claim
from scripts.proof.trusted_repo_change_verifier import verify_trusted_repo_change_bundle_payload


def verify_governed_change_packet_payload(packet: dict[str, Any], *, evidence_ref: str = "") -> dict[str, Any]:
    packet_clean = copy.deepcopy(packet)
    packet_clean.pop("diff_ledger", None)
    checks: list[dict[str, str]] = []
    missing_evidence: list[str] = []
    contradictions: list[str] = []
    manifest = [item for item in packet_clean.get("artifact_manifest") or [] if isinstance(item, dict)]
    manifest_by_role = {str(item.get("role") or ""): item for item in manifest}
    role_diagnostics = _required_role_diagnostics(manifest_by_role)
    authority_ref_diagnostics: list[dict[str, Any]] = []

    _check(checks, "packet_schema_version", packet_clean.get("schema_version") == GOVERNED_CHANGE_PACKET_SCHEMA_VERSION, contradictions, "packet_schema_mismatch")
    _check(checks, "packet_family", packet_clean.get("packet_family") == GOVERNED_CHANGE_PACKET_FAMILY, contradictions, "packet_family_mismatch")
    _check(checks, "packet_compare_scope", packet_clean.get("compare_scope") == TRUSTED_REPO_COMPARE_SCOPE, contradictions, "packet_compare_scope_mismatch")
    _check(checks, "packet_operator_surface", packet_clean.get("operator_surface") == OPERATOR_SURFACE, contradictions, "packet_operator_surface_mismatch")
    _check(
        checks,
        "packet_entry_disclaimer_present",
        "Claim-bearing checks resolve to the underlying authority artifacts" in str(packet_clean.get("packet_entry_disclaimer") or ""),
        contradictions,
        "packet_entry_disclaimer_missing",
    )
    operator_summary_entry = manifest_by_role.get("operator_summary")
    if operator_summary_entry is not None and str(operator_summary_entry.get("classification") or "") != ENTRY_PROJECTION_CLASSIFICATION:
        contradictions.append("packet_operator_summary_masquerades_as_authority")

    for diagnostic in role_diagnostics:
        role = diagnostic["role"]
        _check(checks, f"packet_required_role:{role}", diagnostic["status"] == "pass", [], "")
        missing_evidence.extend(diagnostic["missing_evidence"])
        contradictions.extend(diagnostic["contradictions"])

    if contradictions:
        return _build_report(
            packet=packet_clean,
            evidence_ref=evidence_ref,
            checks=checks,
            packet_verdict="invalid",
            missing_evidence=missing_evidence,
            contradictions=contradictions,
            claim_tier="",
            allowed_claims=[],
            forbidden_claims=[],
            required_role_diagnostics=role_diagnostics,
            authority_ref_diagnostics=authority_ref_diagnostics,
        )

    if missing_evidence:
        return _build_report(
            packet=packet_clean,
            evidence_ref=evidence_ref,
            checks=checks,
            packet_verdict="insufficient_evidence",
            missing_evidence=missing_evidence,
            contradictions=[],
            claim_tier="",
            allowed_claims=[],
            forbidden_claims=[],
            required_role_diagnostics=role_diagnostics,
            authority_ref_diagnostics=authority_ref_diagnostics,
        )

    loaded: dict[str, dict[str, Any]] = {}
    for role in REQUIRED_PACKET_ARTIFACT_ROLES:
        diagnostic, payload = _load_authority_ref(role, manifest_by_role[role])
        authority_ref_diagnostics.append(diagnostic)
        _check(checks, f"packet_authority_ref:{role}", diagnostic["status"] == "pass", [], "")
        if diagnostic["status"] == "pass" and payload is not None:
            loaded[role] = payload
        elif diagnostic["status"] == "digest_mismatch":
            contradictions.append(f"packet_ref_digest_mismatch:{role}")
        else:
            missing_evidence.append(f"packet_ref_unavailable:{role}")

    if contradictions:
        return _build_report(
            packet=packet_clean,
            evidence_ref=evidence_ref,
            checks=checks,
            packet_verdict="invalid",
            missing_evidence=missing_evidence,
            contradictions=contradictions,
            claim_tier="",
            allowed_claims=[],
            forbidden_claims=[],
            required_role_diagnostics=role_diagnostics,
            authority_ref_diagnostics=authority_ref_diagnostics,
        )

    if missing_evidence:
        return _build_report(
            packet=packet_clean,
            evidence_ref=evidence_ref,
            checks=checks,
            packet_verdict="insufficient_evidence",
            missing_evidence=missing_evidence,
            contradictions=[],
            claim_tier="",
            allowed_claims=[],
            forbidden_claims=[],
            required_role_diagnostics=role_diagnostics,
            authority_ref_diagnostics=authority_ref_diagnostics,
        )

    bundle_report = verify_trusted_repo_change_bundle_payload(
        loaded["witness_bundle"],
        evidence_ref=str(manifest_by_role["witness_bundle"]["path"] or ""),
    )
    offline_report = evaluate_trusted_repo_change_offline_claim(
        loaded["campaign_report"],
        requested_claims=[TARGET_CLAIM_TIER],
        evidence_ref=str(manifest_by_role["campaign_report"]["path"] or ""),
    )
    conformance = evaluate_governed_change_packet_kernel_conformance(
        bundle=loaded["witness_bundle"],
        live_report=loaded["approved_live_proof"],
        campaign_report=loaded["campaign_report"],
        offline_report=offline_report,
        model_report=loaded["trusted_kernel_model_check"],
        artifact_refs={role: str(manifest_by_role[role]["path"] or "") for role in REQUIRED_PACKET_ARTIFACT_ROLES},
    )
    contradictions.extend(_packet_summary_contradictions(packet_clean, loaded, bundle_report, offline_report, conformance))
    if contradictions:
        return _build_report(
            packet=packet_clean,
            evidence_ref=evidence_ref,
            checks=checks,
            packet_verdict="invalid",
            missing_evidence=list(bundle_report.get("missing_evidence") or []),
            contradictions=contradictions,
            claim_tier=str(offline_report.get("claim_tier") or ""),
            allowed_claims=list(offline_report.get("allowed_claims") or []),
            forbidden_claims=list(offline_report.get("forbidden_claims") or []),
            required_role_diagnostics=role_diagnostics,
            authority_ref_diagnostics=authority_ref_diagnostics,
        )

    if bundle_report.get("observed_result") != "success" or conformance.get("result") != "pass":
        combined_missing = list(bundle_report.get("missing_evidence") or []) + list(conformance.get("missing_or_failed_obligations") or [])
        return _build_report(
            packet=packet_clean,
            evidence_ref=evidence_ref,
            checks=checks,
            packet_verdict="insufficient_evidence",
            missing_evidence=_unique(combined_missing),
            contradictions=[],
            claim_tier=str(offline_report.get("claim_tier") or ""),
            allowed_claims=list(offline_report.get("allowed_claims") or []),
            forbidden_claims=list(offline_report.get("forbidden_claims") or []),
            required_role_diagnostics=role_diagnostics,
            authority_ref_diagnostics=authority_ref_diagnostics,
        )

    requested_claim = str(packet_clean.get("claim_summary", {}).get("requested_claim_tier") or TARGET_CLAIM_TIER)
    if requested_claim not in list(offline_report.get("allowed_claims") or []):
        return _build_report(
            packet=packet_clean,
            evidence_ref=evidence_ref,
            checks=checks,
            packet_verdict="insufficient_evidence",
            missing_evidence=[f"requested_claim_not_allowed:{requested_claim}"],
            contradictions=[],
            claim_tier=str(offline_report.get("claim_tier") or ""),
            allowed_claims=list(offline_report.get("allowed_claims") or []),
            forbidden_claims=list(offline_report.get("forbidden_claims") or []),
            required_role_diagnostics=role_diagnostics,
            authority_ref_diagnostics=authority_ref_diagnostics,
        )

    return _build_report(
        packet=packet_clean,
        evidence_ref=evidence_ref,
        checks=checks,
        packet_verdict="valid",
        missing_evidence=[],
        contradictions=[],
        claim_tier=str(offline_report.get("claim_tier") or ""),
        allowed_claims=list(offline_report.get("allowed_claims") or []),
        forbidden_claims=list(offline_report.get("forbidden_claims") or []),
        required_role_diagnostics=role_diagnostics,
        authority_ref_diagnostics=authority_ref_diagnostics,
    )


def _packet_summary_contradictions(
    packet: dict[str, Any],
    loaded: dict[str, dict[str, Any]],
    bundle_report: dict[str, Any],
    offline_report: dict[str, Any],
    conformance: dict[str, Any],
) -> list[str]:
    contradictions: list[str] = []
    summary = packet.get("primary_operator_summary") if isinstance(packet.get("primary_operator_summary"), dict) else {}
    claim_summary = packet.get("claim_summary") if isinstance(packet.get("claim_summary"), dict) else {}
    live = loaded["approved_live_proof"]
    bundle = loaded["witness_bundle"]
    validator = loaded["validator_report"]
    offline_artifact = loaded["offline_verifier_report"]
    if summary.get("session_id") != live.get("session_id"):
        contradictions.append("packet_summary_session_id_mismatch")
    if summary.get("run_id") != live.get("run_id"):
        contradictions.append("packet_summary_run_id_mismatch")
    if summary.get("workflow_result") != live.get("workflow_result"):
        contradictions.append("packet_workflow_result_mismatch")
    if summary.get("validator_result") != live.get("validator_result", {}).get("validation_result"):
        contradictions.append("packet_validator_result_mismatch")
    if summary.get("target_artifact_path") != bundle.get("trusted_repo_change_slice", {}).get("artifact_path"):
        contradictions.append("packet_target_artifact_mismatch")
    if summary.get("target_artifact_path") != validator.get("artifact_path"):
        contradictions.append("packet_validator_artifact_mismatch")
    if claim_summary.get("current_truthful_claim_ceiling") != offline_report.get("claim_tier"):
        contradictions.append("packet_claim_ceiling_mismatch")
    if offline_artifact.get("claim_tier") != offline_report.get("claim_tier"):
        contradictions.append("packet_offline_verifier_claim_tier_mismatch")
    if offline_artifact.get("claim_status") != offline_report.get("claim_status"):
        contradictions.append("packet_offline_verifier_claim_status_mismatch")
    if packet.get("trusted_kernel", {}).get("conformance", {}).get("result") not in {"", conformance.get("result")}:
        contradictions.append("packet_kernel_conformance_mismatch")
    if packet.get("trusted_kernel", {}).get("model_check", {}).get("observed_result") not in {"", loaded["trusted_kernel_model_check"].get("observed_result")}:
        contradictions.append("packet_kernel_model_mismatch")
    if bundle_report.get("observed_result") != "success":
        contradictions.append("packet_bundle_verification_not_success")
    return contradictions


def _build_report(
    *,
    packet: dict[str, Any],
    evidence_ref: str,
    checks: list[dict[str, str]],
    packet_verdict: str,
    missing_evidence: list[str],
    contradictions: list[str],
    claim_tier: str,
    allowed_claims: list[str],
    forbidden_claims: list[dict[str, Any]],
    required_role_diagnostics: list[dict[str, Any]],
    authority_ref_diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    observed_result = "success" if packet_verdict == "valid" else ("partial success" if packet_verdict == "insufficient_evidence" else "failure")
    observed_path = "primary" if packet_verdict == "valid" else "blocked"
    unique_missing = _unique(missing_evidence)
    unique_contradictions = _unique(contradictions)
    report = {
        "schema_version": GOVERNED_CHANGE_PACKET_VERIFIER_SCHEMA_VERSION,
        "verified_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": observed_path,
        "observed_result": observed_result,
        "packet_verdict": packet_verdict,
        "packet_id": str(packet.get("packet_id") or ""),
        "compare_scope": str(packet.get("compare_scope") or ""),
        "operator_surface": str(packet.get("operator_surface") or ""),
        "evidence_ref": evidence_ref,
        "checks": checks,
        "required_role_diagnostics": required_role_diagnostics,
        "authority_ref_diagnostics": authority_ref_diagnostics,
        "claim_diagnostics": _claim_diagnostics(
            packet=packet,
            packet_verdict=packet_verdict,
            claim_tier=claim_tier,
            allowed_claims=allowed_claims,
            forbidden_claims=forbidden_claims,
            missing_evidence=unique_missing,
            contradictions=unique_contradictions,
        ),
        "missing_evidence": unique_missing,
        "contradictions": unique_contradictions,
        "claim_tier": claim_tier,
        "allowed_claims": allowed_claims,
        "forbidden_claims": forbidden_claims,
        "side_effect_free_verification": True,
    }
    report["report_signature_digest"] = stable_signature_digest(packet_verifier_signature_material(report))
    return report


def _check(checks: list[dict[str, str]], check_id: str, passed: bool, failures: list[str], failure_code: str) -> None:
    checks.append({"id": check_id, "status": "pass" if passed else "fail"})
    if not passed:
        failures.append(failure_code)


def _required_role_diagnostics(manifest_by_role: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for role in REQUIRED_PACKET_ARTIFACT_ROLES:
        item = manifest_by_role.get(role)
        missing: list[str] = []
        contradictions: list[str] = []
        if item is None:
            missing.append(f"packet_missing_required_role:{role}")
            diagnostics.append(
                {
                    "role": role,
                    "status": "missing",
                    "classification": "",
                    "required": True,
                    "path": "",
                    "exists": False,
                    "missing_evidence": missing,
                    "contradictions": contradictions,
                }
            )
            continue

        classification = str(item.get("classification") or "")
        exists = item.get("exists") is True
        if classification not in PRIMARY_AUTHORITY_CLASSIFICATIONS:
            contradictions.append(f"packet_role_classification_invalid:{role}")
        if not exists:
            missing.append(f"packet_ref_missing:{role}")
        status = "pass"
        if contradictions:
            status = "invalid_classification"
        elif missing:
            status = "missing_ref"
        diagnostics.append(
            {
                "role": role,
                "status": status,
                "classification": classification,
                "required": item.get("required") is True,
                "path": str(item.get("path") or ""),
                "exists": exists,
                "digest": str(item.get("digest") or ""),
                "schema_version": str(item.get("schema_version") or ""),
                "missing_evidence": missing,
                "contradictions": contradictions,
            }
        )
    return diagnostics


def _load_authority_ref(role: str, manifest_item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    ref = str(manifest_item.get("path") or "")
    declared_digest = str(manifest_item.get("digest") or "")
    resolved = resolve_repo_path(ref)
    diagnostic: dict[str, Any] = {
        "role": role,
        "status": "unavailable",
        "path": ref,
        "declared_digest": declared_digest,
        "actual_digest": "",
        "schema_version": "",
        "load_error": "",
    }
    if not ref or not resolved.exists():
        diagnostic["load_error"] = "missing_authority_ref"
        return diagnostic, None
    try:
        actual_digest = json_file_digest(resolved)
        payload = load_json_object(resolved)
    except (OSError, ValueError) as exc:
        diagnostic["load_error"] = f"{type(exc).__name__}:{exc}"
        return diagnostic, None

    diagnostic["actual_digest"] = actual_digest
    diagnostic["schema_version"] = str(payload.get("schema_version") or "")
    if declared_digest and declared_digest != actual_digest:
        diagnostic["status"] = "digest_mismatch"
        return diagnostic, payload
    diagnostic["status"] = "pass"
    return diagnostic, payload


def _claim_diagnostics(
    *,
    packet: dict[str, Any],
    packet_verdict: str,
    claim_tier: str,
    allowed_claims: list[str],
    forbidden_claims: list[dict[str, Any]],
    missing_evidence: list[str],
    contradictions: list[str],
) -> dict[str, Any]:
    claim_summary = packet.get("claim_summary") if isinstance(packet.get("claim_summary"), dict) else {}
    requested_claim = str(claim_summary.get("requested_claim_tier") or TARGET_CLAIM_TIER)
    allowed = requested_claim in allowed_claims
    downgrade_or_rejection_reasons = [
        item
        for item in missing_evidence + contradictions
        if item.startswith("requested_claim_not_allowed:") or "claim" in item or "overclaim" in item
    ]
    for forbidden in forbidden_claims:
        if forbidden.get("claim_tier") == requested_claim:
            downgrade_or_rejection_reasons.extend(str(item) for item in forbidden.get("missing_evidence") or [])
    return {
        "requested_claim_tier": requested_claim,
        "packet_claim_ceiling": str(claim_summary.get("current_truthful_claim_ceiling") or ""),
        "selected_claim_tier": claim_tier,
        "requested_claim_allowed": allowed,
        "allowed_claims": allowed_claims,
        "forbidden_claims": forbidden_claims,
        "packet_verdict": packet_verdict,
        "downgrade_or_rejection_reasons": _unique(downgrade_or_rejection_reasons),
    }


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
