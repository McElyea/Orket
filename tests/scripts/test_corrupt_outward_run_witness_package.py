from __future__ import annotations

from pathlib import Path

from scripts.proof.corrupt_outward_run_witness_package import corrupt_package
from scripts.proof.verify_outward_run_witness_package import verify_package


BASE = Path("tests/proof_fixtures/outward_run/base_approved_package")


def test_corrupt_package_mutates_package_bytes_and_expected_failure(tmp_path: Path) -> None:
    """Layer: contract. Verifies a deterministic package corruption rejects with the expected code."""
    output = tmp_path / "corrupted"

    result = corrupt_package(base=BASE, output=output, corruption_id="ORP-CORR-075")
    report = verify_package(output)

    assert result["result"] == "created"
    assert result["expected_failure_code"] == "artifact_digest_mismatch"
    assert report["result"] == "rejected"
    assert "artifact_digest_mismatch" in report["missing_evidence"]


def test_corrupt_package_reports_missing_fixture_blocker_without_package_mutation(tmp_path: Path) -> None:
    """Layer: contract. Verifies path-family corruptions without fixtures remain explicit blockers."""
    output = tmp_path / "blocked"

    result = corrupt_package(base=BASE, output=output, corruption_id="ORP-CORR-030")

    assert result["result"] == "blocked"
    assert result["failure_code"] == "base_denied_package_missing"
    assert output.exists() is False
