from __future__ import annotations

from pathlib import Path

from scripts.proof.verify_outward_run_witness_package import verify_package


FIXTURE_ROOT = Path("tests/proof_fixtures/outward_run/base_approved_package")


def test_base_approved_outward_run_package_fixture_verifies_offline() -> None:
    """Layer: contract. Verifies the frozen approved-path package is accepted by the offline verifier."""
    report = verify_package(FIXTURE_ROOT)

    assert report["result"] == "accepted"
    assert report["missing_evidence"] == []


def test_base_approved_outward_run_package_fixture_contains_required_package_files() -> None:
    """Layer: contract. Verifies the frozen approved-path fixture contains the full package surface."""
    assert (FIXTURE_ROOT / "manifest.json").exists()
    assert (FIXTURE_ROOT / "outward_witness_bundle.json").exists()
    assert (FIXTURE_ROOT / "ledger_export.json").exists()
    assert (FIXTURE_ROOT / "artifacts" / "committed_output").exists()
