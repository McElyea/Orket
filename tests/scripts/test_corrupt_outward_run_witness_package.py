from __future__ import annotations

from pathlib import Path

from scripts.proof.corrupt_outward_run_witness_package import corrupt_package
from scripts.proof.verify_outward_run_witness_package import verify_package

BASE = Path("tests/proof_fixtures/outward_run/base_approved_package")
BASE_DENIED = Path("tests/proof_fixtures/outward_run/base_denied_package")
BASE_POLICY_REJECTED = Path("tests/proof_fixtures/outward_run/base_policy_rejected_package")


def test_corrupt_package_mutates_package_bytes_and_expected_failure(tmp_path: Path) -> None:
    """Layer: contract. Verifies a deterministic package corruption rejects with the expected code."""
    output = tmp_path / "corrupted"

    result = corrupt_package(base=BASE, output=output, corruption_id="ORP-CORR-075")
    report = verify_package(output)

    assert result["result"] == "created"
    assert result["expected_failure_code"] == "artifact_digest_mismatch"
    assert report["result"] == "rejected"
    assert "artifact_digest_mismatch" in report["missing_evidence"]


def test_corrupt_denial_package_adds_denied_tool_invocation(tmp_path: Path) -> None:
    """Layer: contract. Verifies ORP-CORR-030 is falsifiable over the denied fixture."""
    output = tmp_path / "denied-corrupted"

    result = corrupt_package(base=BASE_DENIED, output=output, corruption_id="ORP-CORR-030")
    report = verify_package(output, scope="outward_run_write_file_denied_v1")

    assert result["result"] == "created"
    assert result["expected_failure_code"] == "denied_proposal_invoked"
    assert report["result"] == "rejected"
    assert "denied_proposal_invoked" in report["missing_evidence"]


def test_corrupt_denial_package_partial_export_rejects(tmp_path: Path) -> None:
    """Layer: contract. Verifies ORP-CORR-068 is falsifiable over the denied fixture."""
    output = tmp_path / "denied-partial"

    result = corrupt_package(base=BASE_DENIED, output=output, corruption_id="ORP-CORR-068")
    report = verify_package(output, scope="outward_run_write_file_denied_v1")

    assert result["result"] == "created"
    assert result["expected_failure_code"] == "full_ledger_export_required"
    assert report["result"] == "rejected"
    assert "full_ledger_export_required" in report["missing_evidence"]


def test_corrupt_policy_rejected_package_adds_tool_invocation(tmp_path: Path) -> None:
    """Layer: contract. Verifies ORP-CORR-031 is falsifiable over the policy-rejected fixture."""
    output = tmp_path / "policy-rejected-corrupted"

    result = corrupt_package(base=BASE_POLICY_REJECTED, output=output, corruption_id="ORP-CORR-031")
    report = verify_package(output, scope="outward_run_write_file_policy_rejected_v1")

    assert result["result"] == "created"
    assert result["expected_failure_code"] == "policy_rejected_proposal_invoked"
    assert report["result"] == "rejected"
    assert "policy_rejected_proposal_invoked" in report["missing_evidence"]
