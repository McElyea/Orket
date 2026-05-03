from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.verify_outward_run_witness_package import verify_package


FIXTURE_ROOT = Path("tests/proof_fixtures/outward_run/base_denied_package")


def test_base_denied_outward_run_package_fixture_verifies_offline() -> None:
    """Layer: contract. Verifies the frozen denial-path package is accepted by the offline verifier."""
    report = verify_package(FIXTURE_ROOT, scope="outward_run_write_file_denied_v1")

    assert report["result"] == "accepted"
    assert report["missing_evidence"] == []


def test_base_denied_outward_run_package_fixture_contains_required_package_files() -> None:
    """Layer: contract. Verifies the frozen denial fixture has full ledger evidence and no committed artifact."""
    assert (FIXTURE_ROOT / "manifest.json").exists()
    assert (FIXTURE_ROOT / "outward_witness_bundle.json").exists()
    assert (FIXTURE_ROOT / "ledger_export.json").exists()
    assert (FIXTURE_ROOT / "artifacts" / "committed_output").exists() is False
    ledger = json.loads((FIXTURE_ROOT / "ledger_export.json").read_text(encoding="utf-8"))
    event_types = [event["event_type"] for event in ledger["events"]]
    assert ledger["export_scope"] == "all"
    assert "proposal_denied" in event_types
    assert "tool_invoked" not in event_types
    assert "commitment_recorded" not in event_types
