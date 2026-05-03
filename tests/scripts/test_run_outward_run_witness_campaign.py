from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.run_outward_run_witness_campaign import build_campaign_report, main
from scripts.proof.verify_outward_run_witness_package import verify_package


BASE = Path("tests/proof_fixtures/outward_run/base_approved_package")


def test_one_accepted_package_report_cannot_claim_verifier_stable() -> None:
    """Layer: contract. Verifies one accepted report cannot produce campaign stability."""
    report = verify_package(BASE)

    campaign = build_campaign_report([report])

    assert campaign["result"] == "rejected"
    assert campaign["missing_evidence_union"] == ["claim_tier_not_supported"]


def test_matching_accepted_reports_produce_stable_campaign_report() -> None:
    """Layer: contract. Verifies matching accepted reports can claim outward_verifier_stable."""
    report = verify_package(BASE)

    campaign = build_campaign_report([report, dict(report)])

    assert campaign["schema_version"] == "outward_run_campaign_report.v1"
    assert campaign["result"] == "accepted"
    assert campaign["claim_tier_assigned"] == "outward_verifier_stable"
    assert campaign["invariant_signature_stable"] is True


def test_campaign_cli_writes_diff_ledger_report(tmp_path: Path) -> None:
    """Layer: contract. Verifies the campaign command writes rerunnable JSON."""
    report = verify_package(BASE)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    output = tmp_path / "campaign.json"

    exit_code = main(["--report", str(report_path), "--report", str(report_path), "--output", str(output)])
    persisted = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert persisted["result"] == "accepted"
    assert isinstance(persisted["diff_ledger"], list)
