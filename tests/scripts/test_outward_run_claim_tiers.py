from __future__ import annotations

from scripts.proof.outward_run_claim_tiers import assign_claim_tier


def test_single_accepted_report_can_claim_lab_only() -> None:
    """Layer: unit. Verifies one accepted package supports only the lab-only posture."""
    result = assign_claim_tier("outward_lab_only", {"accepted_report_count": 1})

    assert result["result"] == "accepted"
    assert result["claim_tier_assigned"] == "outward_lab_only"


def test_single_accepted_report_cannot_claim_verifier_stable() -> None:
    """Layer: unit. Verifies one package cannot claim campaign stability."""
    result = assign_claim_tier("outward_verifier_stable", {"accepted_report_count": 1})

    assert result["result"] == "rejected"
    assert result["missing_evidence"] == ["claim_tier_not_supported"]


def test_matching_campaign_can_claim_verifier_stable() -> None:
    """Layer: unit. Verifies a stable campaign supports outward_verifier_stable."""
    result = assign_claim_tier(
        "outward_verifier_stable",
        {"accepted_report_count": 2, "invariant_signature_stable": True, "campaign_report_present": True},
    )

    assert result["result"] == "accepted"
    assert result["claim_tier_assigned"] == "outward_verifier_stable"


def test_unlinked_clean_environment_cannot_claim_externally_checkable() -> None:
    """Layer: unit. Verifies externally checkable posture requires all external evidence."""
    result = assign_claim_tier(
        "outward_externally_checkable",
        {"accepted_report_count": 2, "invariant_signature_stable": True, "campaign_report_present": True},
    )

    assert result["result"] == "rejected"


def test_clean_environment_with_corruption_and_assurance_can_claim_externally_checkable() -> None:
    """Layer: unit. Verifies externally checkable posture can be assigned only with its evidence."""
    result = assign_claim_tier(
        "outward_externally_checkable",
        {
            "accepted_report_count": 2,
            "invariant_signature_stable": True,
            "campaign_report_present": True,
            "clean_environment_verified": True,
            "corruption_suite_passed": True,
            "assurance_case_linked": True,
        },
    )

    assert result["result"] == "accepted"


def test_public_trust_requires_trust_contract_update_evidence() -> None:
    """Layer: unit. Verifies public trust is rejected without same-change trust contract evidence."""
    evidence = {
        "accepted_report_count": 2,
        "invariant_signature_stable": True,
        "campaign_report_present": True,
        "clean_environment_verified": True,
        "corruption_suite_passed": True,
        "assurance_case_linked": True,
    }

    assert assign_claim_tier("outward_public_trust", evidence)["result"] == "rejected"
    evidence["trust_reason_contract_updated"] = True
    assert assign_claim_tier("outward_public_trust", evidence)["result"] == "accepted"
