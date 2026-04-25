from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.proof.check_trusted_terraform_plan_fixture import build_fixture_check_report
from scripts.proof.generate_trusted_terraform_plan_fixture import generate_fixture_files
from scripts.proof.trusted_terraform_plan_fixtures import build_plan_fixture

pytestmark = pytest.mark.contract


def test_safe_fixture_parses_and_yields_safe_verdict(tmp_path: Path) -> None:
    metadata = generate_fixture_files(
        fixture_kind="safe",
        fixture_seed="fixture-safe",
        output_dir=tmp_path,
    )
    report = build_fixture_check_report(
        plan_fixture=tmp_path / "terraform-plan.json",
        metadata_path=tmp_path / "terraform-plan-fixture-metadata.json",
    )

    assert metadata["fixture_seed"] == "fixture-safe"
    assert metadata["expected_verdict"] == "safe_for_v1_policy"
    assert report["observed_result"] == "success"
    assert report["actual_verdict"] == "safe_for_v1_policy"


def test_risky_fixture_parses_and_yields_risky_verdict(tmp_path: Path) -> None:
    metadata = generate_fixture_files(
        fixture_kind="risky",
        fixture_seed="fixture-risky",
        output_dir=tmp_path,
    )
    report = build_fixture_check_report(
        plan_fixture=tmp_path / "terraform-plan.json",
        metadata_path=tmp_path / "terraform-plan-fixture-metadata.json",
    )

    assert metadata["expected_verdict"] == "risky_for_v1_policy"
    assert report["observed_result"] == "success"
    assert report["actual_verdict"] == "risky_for_v1_policy"


def test_seed_reproducibility() -> None:
    first = build_plan_fixture(fixture_kind="safe", fixture_seed="same-seed")
    second = build_plan_fixture(fixture_kind="safe", fixture_seed="same-seed")

    assert first.plan_payload == second.plan_payload
    assert first.metadata["plan_hash"] == second.metadata["plan_hash"]


def test_malformed_fixture_fails_closed(tmp_path: Path) -> None:
    plan = tmp_path / "terraform-plan.json"
    metadata = tmp_path / "terraform-plan-fixture-metadata.json"
    plan.write_text("{not-json", encoding="utf-8")
    metadata.write_text(json.dumps({"expected_verdict": "safe_for_v1_policy", "plan_hash": "sha256:bad"}), encoding="utf-8")

    report = build_fixture_check_report(plan_fixture=plan, metadata_path=metadata)

    assert report["observed_path"] == "blocked"
    assert report["observed_result"] == "failure"
    assert "invalid_json_plan" in report["blocking_reasons"]


def test_unsupported_action_mix_fails_closed(tmp_path: Path) -> None:
    plan = tmp_path / "terraform-plan.json"
    metadata = tmp_path / "terraform-plan-fixture-metadata.json"
    payload = {
        "format_version": "1.1",
        "resource_changes": [
            {
                "address": "aws_s3_bucket.bad",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "type": "aws_s3_bucket",
                "change": {"actions": ["read"]},
            }
        ],
    }
    plan.write_text(json.dumps(payload), encoding="utf-8")
    metadata.write_text(json.dumps({"expected_verdict": "safe_for_v1_policy"}), encoding="utf-8")

    report = build_fixture_check_report(plan_fixture=plan, metadata_path=metadata)

    assert report["observed_result"] == "failure"
    assert "unsupported_action_mix" in report["blocking_reasons"]
