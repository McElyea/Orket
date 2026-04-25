from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.proof.check_no_credentials_in_generated_artifacts import main as credential_scan_main
from scripts.proof.check_trusted_terraform_live_setup_preflight import main as preflight_main
from scripts.proof.check_trusted_terraform_plan_fixture import main as fixture_check_main
from scripts.proof.prepare_northstar_disposable_aws_smoke_packet import main as packet_main
from scripts.proof.run_trusted_terraform_disposable_aws_setup import main as setup_main

pytestmark = pytest.mark.integration


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_disposable_smoke_no_spend_path_runs_without_aws_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", raising=False)
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", raising=False)
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    assert packet_main(["--seed", "no-spend-seed", "--fixture-kind", "safe", "--fixture-seed", "fixture-seed", "--output-dir", str(tmp_path)]) == 0
    assert fixture_check_main(
        [
            "--plan-fixture",
            str(tmp_path / "terraform-plan.json"),
            "--metadata",
            str(tmp_path / "terraform-plan-fixture-metadata.json"),
            "--output",
            str(tmp_path / "terraform-plan-fixture-check.json"),
        ]
    ) == 0
    assert preflight_main(["--packet-dir", str(tmp_path), "--output", str(tmp_path / "preflight.json")]) == 0
    assert setup_main(["--packet-dir", str(tmp_path), "--output", str(tmp_path / "aws-setup-result.json")]) == 1
    assert credential_scan_main(["--scan-root", str(tmp_path), "--output", str(tmp_path / "credential-scan.json")]) == 0

    packet = _load(tmp_path / "northstar-disposable-aws-smoke-packet.json")
    preflight = _load(tmp_path / "preflight.json")
    setup = _load(tmp_path / "aws-setup-result.json")
    scan = _load(tmp_path / "credential-scan.json")

    assert packet["provider_calls_executed"] == []
    assert preflight["provider_calls_executed"] == []
    assert preflight["observed_path"] == "primary"
    assert preflight["observed_result"] == "success"
    assert setup["provider_calls_executed"] == []
    assert setup["observed_result"] == "environment blocker"
    assert scan["credential_values_recorded"] is False
