from __future__ import annotations

from typing import Any

from scripts.proof.trusted_scope_family_support import (
    ValidatorBackedScopeConfig,
    build_validator_backed_campaign_report,
    evaluate_validator_backed_scope_offline_claim,
)

_CONFIG = ValidatorBackedScopeConfig(
    compare_scope="trusted_scope_family_test_v1",
    operator_surface="trusted_run_witness_report.v1",
    fallback_claim_tier="non_deterministic_lab_only",
    target_claim_tier="verdict_deterministic",
)


def test_bundle_input_uses_shared_helper_and_stays_lab_only() -> None:
    """Layer: contract. Verifies the shared validator-backed helper recomputes bundle evidence and preserves the fallback claim tier."""
    report = evaluate_validator_backed_scope_offline_claim(
        {"schema_version": _CONFIG.bundle_schema_version, "bundle_id": "bundle-a"},
        config=_CONFIG,
        verify_bundle_payload=_verify_bundle_payload,
        requested_claims=[_CONFIG.fallback_claim_tier],
    )

    assert report["input_mode"] == "bundle"
    assert report["claim_status"] == "allowed"
    assert report["claim_tier"] == _CONFIG.fallback_claim_tier
    assert report["allowed_claims"] == [_CONFIG.fallback_claim_tier]


def test_campaign_report_reaches_scope_target_claim_when_signatures_stable() -> None:
    """Layer: contract. Verifies the shared helper promotes only the target claim tier from stable repeated validator-backed evidence."""
    campaign = build_validator_backed_campaign_report(
        [_single_report(bundle_id="bundle-a"), _single_report(bundle_id="bundle-b")],
        config=_CONFIG,
        must_catch_outcomes=["missing_final_truth", "validator_failed"],
        bundle_refs=["runs/a/bundle.json", "runs/b/bundle.json"],
        live_proof_refs=["proof/a.json", "proof/b.json"],
    )

    report = evaluate_validator_backed_scope_offline_claim(
        campaign,
        config=_CONFIG,
        verify_bundle_payload=_verify_bundle_payload,
        requested_claims=[_CONFIG.target_claim_tier],
    )

    assert campaign["observed_result"] == "success"
    assert campaign["claim_tier"] == _CONFIG.target_claim_tier
    assert campaign["bundle_refs"] == ["runs/a/bundle.json", "runs/b/bundle.json"]
    assert campaign["live_proof_refs"] == ["proof/a.json", "proof/b.json"]
    assert report["claim_status"] == "allowed"
    assert report["claim_tier"] == _CONFIG.target_claim_tier
    assert report["allowed_claims"] == [_CONFIG.fallback_claim_tier, _CONFIG.target_claim_tier]


def test_campaign_signature_drift_downgrades_through_shared_helper() -> None:
    """Layer: contract. Verifies signature drift on the shared helper forbids the higher claim without hiding the lower proven claim."""
    first = _single_report(bundle_id="bundle-a")
    second = _single_report(bundle_id="bundle-b")
    second["validator_signature_digest"] = "sha256:different"
    campaign = build_validator_backed_campaign_report(
        [first, second],
        config=_CONFIG,
        must_catch_outcomes=["missing_final_truth", "validator_failed"],
    )

    report = evaluate_validator_backed_scope_offline_claim(
        campaign,
        config=_CONFIG,
        verify_bundle_payload=_verify_bundle_payload,
        requested_claims=[_CONFIG.target_claim_tier],
    )

    assert campaign["observed_result"] == "partial success"
    assert report["claim_status"] == "downgraded"
    assert report["claim_tier"] == _CONFIG.fallback_claim_tier
    assert report["allowed_claims"] == [_CONFIG.fallback_claim_tier]
    assert "validator_signature_not_stable" in _forbidden_reasons(report, _CONFIG.target_claim_tier)


def _verify_bundle_payload(bundle: dict[str, Any], *, evidence_ref: str = "") -> dict[str, Any]:
    return _single_report(bundle_id=str(bundle.get("bundle_id") or "bundle-a"), evidence_ref=evidence_ref)


def _single_report(*, bundle_id: str, evidence_ref: str = "") -> dict[str, Any]:
    return {
        "schema_version": _CONFIG.report_schema_version,
        "observed_result": "success",
        "claim_tier": _CONFIG.fallback_claim_tier,
        "compare_scope": _CONFIG.compare_scope,
        "operator_surface": _CONFIG.operator_surface,
        "bundle_id": bundle_id,
        "run_id": f"run:{bundle_id}",
        "session_id": f"session:{bundle_id}",
        "policy_digest": "sha256:policy",
        "control_bundle_ref": "control/bundle.json",
        "evidence_ref": evidence_ref,
        "side_effect_free_verification": True,
        "contract_verdict": {"verdict_signature_digest": "sha256:verdict"},
        "validator_signature_digest": "sha256:validator",
        "invariant_model_signature_digest": "sha256:invariant",
        "substrate_signature_digest": "sha256:substrate",
        "must_catch_outcomes": ["missing_final_truth", "validator_failed"],
        "missing_evidence": [],
    }


def _forbidden_reasons(report: dict[str, Any], claim_tier: str) -> list[str]:
    for item in report.get("forbidden_claims") or []:
        if item.get("claim_tier") == claim_tier:
            return list(item.get("reason_codes") or [])
    return []
