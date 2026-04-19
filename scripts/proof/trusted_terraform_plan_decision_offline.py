from __future__ import annotations

from scripts.proof.trusted_terraform_plan_decision_contract import (
    BUNDLE_SCHEMA_VERSION,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
)
from scripts.proof.trusted_terraform_plan_decision_verifier import verify_trusted_terraform_plan_decision_bundle_payload
from scripts.proof.trusted_scope_family_support import (
    ValidatorBackedScopeConfig,
    evaluate_validator_backed_scope_offline_claim,
)

_CONFIG = ValidatorBackedScopeConfig(
    compare_scope=TRUSTED_TERRAFORM_COMPARE_SCOPE,
    operator_surface=OPERATOR_SURFACE,
    fallback_claim_tier=FALLBACK_CLAIM_TIER,
    target_claim_tier=TARGET_CLAIM_TIER,
    bundle_schema_version=BUNDLE_SCHEMA_VERSION,
    report_schema_version=REPORT_SCHEMA_VERSION,
)


def evaluate_trusted_terraform_plan_decision_offline_claim(
    payload: dict[str, Any],
    *,
    input_mode: str = "auto",
    requested_claims: list[str] | None = None,
    evidence_ref: str = "",
) -> dict[str, Any]:
    return evaluate_validator_backed_scope_offline_claim(
        payload,
        config=_CONFIG,
        verify_bundle_payload=verify_trusted_terraform_plan_decision_bundle_payload,
        input_mode=input_mode,
        requested_claims=requested_claims,
        evidence_ref=evidence_ref,
    )
