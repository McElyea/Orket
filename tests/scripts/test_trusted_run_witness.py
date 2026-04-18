from __future__ import annotations

import copy
import pytest

from scripts.proof.trusted_run_witness_support import (
    FALLBACK_CLAIM_TIER,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    build_campaign_verification_report,
    verify_witness_bundle_payload,
)
from scripts.proof.trusted_run_invariant_model import evaluate_trusted_run_invariants
from tests.helpers.trusted_run_witness_fixtures import valid_bundle as _valid_bundle

def test_valid_single_bundle_verifies_as_lab_only() -> None:
    """Layer: contract. Verifies a complete bundle passes but remains single-run lab tier."""
    bundle = _valid_bundle()

    report = verify_witness_bundle_payload(bundle, evidence_ref="runs/sess-a/trusted_run_witness_bundle.json")

    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["observed_result"] == "success"
    assert report["claim_tier"] == FALLBACK_CLAIM_TIER
    assert report["contract_verdict"]["verdict"] == "pass"
    assert report["trusted_run_invariant_model"]["result"] == "pass"
    assert report["invariant_model_signature_digest"].startswith("sha256:")


def test_invariant_model_accepts_valid_trace() -> None:
    """Layer: contract. Verifies the bounded invariant model accepts complete evidence."""
    model = evaluate_trusted_run_invariants(_valid_bundle())

    assert model["result"] == "pass"
    assert model["missing_proof_blockers"] == []
    assert {item["status"] for item in model["checked_invariants"]} == {"pass"}


def test_invariant_model_rejects_illegal_step_lineage() -> None:
    """Layer: contract. Verifies effect evidence must be explainable by step lineage."""
    bundle = _valid_bundle()
    bundle["authority_lineage"]["step"]["latest_step_id"] = "orphan-step"

    model = evaluate_trusted_run_invariants(bundle)

    assert model["result"] == "fail"
    assert "step_lineage_missing_or_drifted" in model["failures"]


def test_invariant_model_rejects_resource_lease_drift() -> None:
    """Layer: contract. Verifies resource authority cannot contradict lease provenance."""
    bundle = _valid_bundle()
    bundle["authority_lineage"]["resource"]["provenance_ref"] = "turn-tool-lease:other-run"

    model = evaluate_trusted_run_invariants(bundle)

    assert model["result"] == "fail"
    assert "resource_lease_consistency_not_verified" in model["failures"]


def test_verifier_does_not_mutate_bundle_payload() -> None:
    """Layer: contract. Verifies bundle evaluation is side-effect-free over input payloads."""
    bundle = _valid_bundle()
    before = copy.deepcopy(bundle)

    report = verify_witness_bundle_payload(bundle)

    assert report["side_effect_free_verification"] is True
    assert bundle == before


def test_run_id_drift_fails_verification() -> None:
    """Layer: contract. Verifies canonical run-id drift is a fail-closed verifier error."""
    bundle = _valid_bundle()
    bundle["authority_lineage"]["run"]["run_id"] = "turn-tool-run:sess-b:PF-WRITE-1:lead_architect:0001"

    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure"
    assert "canonical_run_id_drift" in report["missing_evidence"]


def test_missing_final_truth_fails_verification() -> None:
    """Layer: contract. Verifies a success-claiming bundle cannot omit final truth."""
    bundle = _valid_bundle()
    bundle["authority_lineage"].pop("final_truth")

    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure"
    assert "missing_final_truth" in report["missing_evidence"]


def test_missing_contract_verdict_fails_verification() -> None:
    """Layer: contract. Verifies the deterministic verdict surface is required evidence."""
    bundle = _valid_bundle()
    bundle.pop("contract_verdict")

    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure"
    assert "contract_verdict_missing" in report["missing_evidence"]


def test_wrong_output_content_fails_contract_verdict() -> None:
    """Layer: contract. Verifies mutated normalized content fails the deterministic verdict."""
    bundle = _valid_bundle()
    bundle["observed_effect"]["normalized_content"] = "rejected"

    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure"
    assert "wrong_output_content" in report["missing_evidence"]


def test_two_matching_reports_claim_verdict_deterministic() -> None:
    """Layer: contract. Verifies repeat evidence promotes only stable verdict signatures."""
    first = verify_witness_bundle_payload(_valid_bundle(session_id="sess-a"))
    second = verify_witness_bundle_payload(_valid_bundle(session_id="sess-b"))

    campaign = build_campaign_verification_report([first, second])

    assert campaign["observed_result"] == "success"
    assert campaign["claim_tier"] == TARGET_CLAIM_TIER
    assert len(campaign["verdict_signature_digests"]) == 1
    assert len(campaign["invariant_model_signature_digests"]) == 1


def test_campaign_rejects_unstable_invariant_signature() -> None:
    """Layer: contract. Verifies deterministic claims require stable invariant signatures."""
    first = verify_witness_bundle_payload(_valid_bundle(session_id="sess-a"))
    second = verify_witness_bundle_payload(_valid_bundle(session_id="sess-b"))
    second["invariant_model_signature_digest"] = "sha256:different"

    campaign = build_campaign_verification_report([first, second])

    assert campaign["observed_result"] != "success"
    assert campaign["claim_tier"] == FALLBACK_CLAIM_TIER
    assert "invariant_model_signature_not_stable" in campaign["missing_evidence"]


def test_campaign_rejects_missing_side_effect_free_proof() -> None:
    """Layer: contract. Verifies campaigns fail closed when verifier purity proof is missing."""
    first = verify_witness_bundle_payload(_valid_bundle(session_id="sess-a"))
    second = verify_witness_bundle_payload(_valid_bundle(session_id="sess-b"))
    second.pop("side_effect_free_verification")

    campaign = build_campaign_verification_report([first, second])

    assert campaign["observed_result"] != "success"
    assert "verifier_side_effect_absence_not_mechanically_proven" in campaign["missing_evidence"]


@pytest.mark.parametrize(
    ("corruption_id", "mutate", "expected"),
    [
        ("MFI-CORR-001", lambda item: item.__setitem__("schema_version", "bad"), "schema_version_missing_or_unsupported"),
        ("MFI-CORR-002", lambda item: item.__setitem__("compare_scope", "other"), "compare_scope_missing_or_unsupported"),
        ("MFI-CORR-003", lambda item: item.__setitem__("operator_surface", "other"), "operator_surface_missing"),
        ("MFI-CORR-004", lambda item: item.pop("run_id"), "canonical_run_id_drift"),
        ("MFI-CORR-005", lambda item: item["authority_lineage"]["run"].__setitem__("run_id", "other"), "canonical_run_id_drift"),
        (
            "MFI-CORR-006",
            lambda item: item["authority_lineage"]["approval_request"].__setitem__("control_plane_target_ref", "other"),
            "approval_request_missing_or_drifted",
        ),
        (
            "MFI-CORR-007",
            lambda item: item["authority_lineage"]["checkpoint"].__setitem__("checkpoint_id", "turn-tool-checkpoint:other"),
            "checkpoint_missing_or_drifted",
        ),
        ("MFI-CORR-008", lambda item: item.pop("policy_digest"), "policy_or_configuration_missing"),
        ("MFI-CORR-009", lambda item: item.pop("configuration_snapshot_ref"), "policy_or_configuration_missing"),
        ("MFI-CORR-010", lambda item: item["artifact_refs"][0].pop("digest"), "artifact_ref_missing"),
        ("MFI-CORR-011", lambda item: item["artifact_refs"][1].pop("digest"), "artifact_ref_missing"),
        ("MFI-CORR-012", lambda item: item["authority_lineage"]["governed_input"].__setitem__("epic_id", "other"), "governed_input_missing"),
        ("MFI-CORR-013", lambda item: item["authority_lineage"].pop("operator_action"), "missing_approval_resolution"),
        ("MFI-CORR-014", lambda item: item["authority_lineage"]["operator_action"].__setitem__("result", "denied"), "missing_approval_resolution"),
        (
            "MFI-CORR-015",
            lambda item: item["authority_lineage"]["checkpoint"].__setitem__("acceptance_dependent_lease_refs", []),
            "resource_or_lease_evidence_missing",
        ),
        (
            "MFI-CORR-016",
            lambda item: item["authority_lineage"]["resource"].__setitem__("resource_id", "namespace:issue:OTHER"),
            "resource_or_lease_evidence_missing",
        ),
        ("MFI-CORR-017", lambda item: item["authority_lineage"].pop("effect_journal"), "missing_effect_evidence"),
        ("MFI-CORR-018", lambda item: item["authority_lineage"]["effect_journal"].__setitem__("effect_entry_count", 1), "missing_effect_evidence"),
        (
            "MFI-CORR-019",
            lambda item: item["authority_lineage"]["effect_journal"].__setitem__("latest_uncertainty_classification", "uncertain"),
            "missing_effect_evidence",
        ),
        ("MFI-CORR-020", lambda item: item["observed_effect"].__setitem__("actual_output_artifact_path", "other.txt"), "missing_output_artifact"),
        ("MFI-CORR-021", lambda item: item["observed_effect"].__setitem__("normalized_content", "rejected"), "wrong_output_content"),
        ("MFI-CORR-022", lambda item: item["observed_effect"].__setitem__("issue_status", "code_review"), "wrong_terminal_issue_status"),
        ("MFI-CORR-023", lambda item: item["authority_lineage"].pop("final_truth"), "missing_final_truth"),
        ("MFI-CORR-024", lambda item: item["authority_lineage"]["final_truth"].__setitem__("result_class", "failed"), "missing_final_truth"),
        ("MFI-CORR-025", lambda item: item.pop("contract_verdict"), "contract_verdict_missing"),
        (
            "MFI-CORR-026",
            lambda item: item["contract_verdict"].__setitem__("verdict_signature_digest", "sha256:drift"),
            "contract_verdict_drift",
        ),
        (
            "MFI-CORR-029",
            lambda item: item["resolution_basis"].__setitem__("run_summary_path", "runs/other/run_summary.json"),
            "canonical_run_id_drift",
        ),
    ],
)
def test_serialized_corruption_matrix_fails_closed(corruption_id: str, mutate: object, expected: str) -> None:
    """Layer: contract. Verifies serialized witness corruptions fail closed."""
    bundle = _valid_bundle()

    mutate(bundle)
    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure", corruption_id
    assert expected in report["missing_evidence"], corruption_id


def test_single_report_campaign_stays_lab_only() -> None:
    """Layer: contract. Verifies one successful report cannot claim deterministic verdicts."""
    report = verify_witness_bundle_payload(_valid_bundle())

    campaign = build_campaign_verification_report([report])

    assert campaign["claim_tier"] == FALLBACK_CLAIM_TIER
    assert "repeat_evidence_missing" in campaign["missing_evidence"]


def test_campaign_rejects_unstable_verdict_signature() -> None:
    """Layer: contract. Verifies campaigns fail when verdict signatures drift."""
    first = verify_witness_bundle_payload(_valid_bundle(session_id="sess-a"))
    second = verify_witness_bundle_payload(_valid_bundle(session_id="sess-b"))
    second["contract_verdict"]["verdict_signature_digest"] = "sha256:different"

    campaign = build_campaign_verification_report([first, second])

    assert campaign["claim_tier"] == FALLBACK_CLAIM_TIER
    assert "verdict_signature_not_stable" in campaign["missing_evidence"]


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda item: item["authority_lineage"].pop("reservation"), "lease_source_reservation_not_verified"),
        (lambda item: item["authority_lineage"]["effect_journal"].pop("latest_prior_entry_digest"), "effect_prior_chain_not_verified"),
        (
            lambda item: item["authority_lineage"]["run"].__setitem__("final_truth_record_id", "turn-tool-final-truth:other"),
            "final_truth_cardinality_not_verified",
        ),
    ],
)
def test_former_missing_proof_blockers_are_mechanically_checked(mutate: object, expected: str) -> None:
    """Layer: contract. Verifies formerly named blockers now produce concrete failures."""
    bundle = _valid_bundle()

    mutate(bundle)
    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure"
    assert expected in report["missing_evidence"]
