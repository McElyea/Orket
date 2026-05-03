from __future__ import annotations

from typing import Any


POSTURES = [
    "outward_lab_only",
    "outward_verifier_stable",
    "outward_externally_checkable",
    "outward_public_trust",
]


def assign_claim_tier(requested: str, evidence: dict[str, Any]) -> dict[str, Any]:
    clean_requested = str(requested or "outward_lab_only").strip()
    if clean_requested not in POSTURES:
        return _rejected(clean_requested, "claim_tier_not_supported", "outward_lab_only")
    ceiling = evidence_supported_ceiling(evidence)
    if _rank(clean_requested) > _rank(ceiling):
        return _rejected(clean_requested, "claim_tier_not_supported", ceiling)
    return {
        "result": "accepted",
        "claim_tier_request": clean_requested,
        "claim_tier_assigned": clean_requested,
        "claim_tier_ceiling": ceiling,
        "missing_evidence": [],
    }


def evidence_supported_ceiling(evidence: dict[str, Any]) -> str:
    if _public_trust_supported(evidence):
        return "outward_public_trust"
    if _externally_checkable_supported(evidence):
        return "outward_externally_checkable"
    if _verifier_stable_supported(evidence):
        return "outward_verifier_stable"
    return "outward_lab_only" if int(evidence.get("accepted_report_count") or 0) >= 1 else "none"


def campaign_evidence(reports: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [report for report in reports if report.get("result") == "accepted"]
    signatures = {str(report.get("invariant_signature") or "") for report in accepted}
    signatures.discard("")
    stable = len(accepted) >= 2 and len(accepted) == len(reports) and len(signatures) == 1
    return {
        "accepted_report_count": len(accepted),
        "report_count": len(reports),
        "invariant_signature_stable": stable,
        "invariant_signature": next(iter(signatures)) if len(signatures) == 1 else "",
        "campaign_report_present": stable,
    }


def _verifier_stable_supported(evidence: dict[str, Any]) -> bool:
    return (
        int(evidence.get("accepted_report_count") or 0) >= 2
        and evidence.get("invariant_signature_stable") is True
        and evidence.get("campaign_report_present") is True
    )


def _externally_checkable_supported(evidence: dict[str, Any]) -> bool:
    return (
        _verifier_stable_supported(evidence)
        and evidence.get("clean_environment_verified") is True
        and evidence.get("corruption_suite_passed") is True
        and evidence.get("assurance_case_linked") is True
    )


def _public_trust_supported(evidence: dict[str, Any]) -> bool:
    return _externally_checkable_supported(evidence) and evidence.get("trust_reason_contract_updated") is True


def _rank(posture: str) -> int:
    if posture == "none":
        return -1
    return POSTURES.index(posture)


def _rejected(requested: str, code: str, ceiling: str) -> dict[str, Any]:
    return {
        "result": "rejected",
        "claim_tier_request": requested,
        "claim_tier_assigned": "none",
        "claim_tier_ceiling": ceiling,
        "missing_evidence": [code],
    }
