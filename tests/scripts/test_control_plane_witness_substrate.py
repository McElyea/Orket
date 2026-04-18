from __future__ import annotations

from scripts.proof.control_plane_witness_substrate import evaluate_control_plane_witness_substrate
from scripts.proof.trusted_run_witness_support import (
    FALLBACK_CLAIM_TIER,
    TARGET_CLAIM_TIER,
    build_campaign_verification_report,
    verify_witness_bundle_payload,
)
from tests.scripts.test_trusted_run_witness import _valid_bundle


def test_valid_bundle_includes_passing_substrate_model() -> None:
    """Layer: contract. Verifies complete witness evidence passes substrate checks."""
    bundle = _valid_bundle()

    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "success"
    assert report["control_plane_witness_substrate"]["result"] == "pass"
    assert report["substrate_signature_digest"].startswith("sha256:")


def test_substrate_matrix_classifies_projection_only_surfaces() -> None:
    """Layer: contract. Verifies projection-only families are visible in substrate output."""
    substrate = evaluate_control_plane_witness_substrate(_valid_bundle())
    classifications = {
        item["record_family"]: item["classification"]
        for item in substrate["record_families"]
    }

    assert classifications["run_summary"] == "projection_only"
    assert classifications["review_package"] == "projection_only"
    assert classifications["evidence_graph"] == "projection_only"
    assert classifications["packet_blocks"] == "projection_only"


def test_issue_status_cannot_substitute_for_final_truth() -> None:
    """Layer: contract. Verifies read-model issue status cannot replace final truth."""
    bundle = _valid_bundle()
    bundle["authority_lineage"].pop("final_truth")
    bundle["projection_evidence"] = {
        "run_summary": {
            "status": "completed",
            "source_path": "runs/sess-a/run_summary.json",
        }
    }

    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure"
    assert "missing_final_truth" in report["missing_evidence"]
    assert "projection_substitute_not_authority" in report["missing_evidence"]


def test_output_content_cannot_substitute_for_effect_journal() -> None:
    """Layer: contract. Verifies output content cannot replace effect authority."""
    bundle = _valid_bundle()
    bundle["authority_lineage"].pop("effect_journal")
    bundle["projection_evidence"] = {
        "review_package": {
            "result": "approved",
            "source_path": "runs/sess-a/productflow_review_index.json",
        }
    }

    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure"
    assert "missing_effect_evidence" in report["missing_evidence"]
    assert "projection_substitute_not_authority" in report["missing_evidence"]


def test_projection_evidence_without_source_ref_fails_closed() -> None:
    """Layer: contract. Verifies source-less projection evidence cannot enter proof."""
    bundle = _valid_bundle()
    bundle["projection_evidence"] = {"review_package": {"result": "success"}}

    report = verify_witness_bundle_payload(bundle)

    assert report["observed_result"] == "failure"
    assert "authority_source_ref_missing" in report["missing_evidence"]


def test_campaign_requires_stable_substrate_signature() -> None:
    """Layer: contract. Verifies deterministic campaign claims require substrate stability."""
    first = verify_witness_bundle_payload(_valid_bundle(session_id="sess-a"))
    second = verify_witness_bundle_payload(_valid_bundle(session_id="sess-b"))
    second["substrate_signature_digest"] = "sha256:different"

    campaign = build_campaign_verification_report([first, second])

    assert campaign["claim_tier"] == FALLBACK_CLAIM_TIER
    assert campaign["claim_tier"] != TARGET_CLAIM_TIER
    assert "substrate_signature_not_stable" in campaign["missing_evidence"]
