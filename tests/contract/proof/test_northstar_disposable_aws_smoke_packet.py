from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.proof.prepare_northstar_disposable_aws_smoke_packet import prepare_northstar_disposable_packet

pytestmark = pytest.mark.contract


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_disposable_packet_has_no_placeholders_and_no_provider_calls(tmp_path: Path) -> None:
    packet = prepare_northstar_disposable_packet(
        seed="packet-seed",
        bucket="",
        table_name="",
        key="proof/terraform-plan.json",
        region="us-east-1",
        model_id="us.writer.palmyra-x4-v1:0",
        fixture_kind="safe",
        fixture_seed="fixture-seed",
        output_dir=tmp_path,
    )

    assert packet["observed_result"] == "success"
    assert packet["provider_calls_executed"] == []
    assert "<" not in packet["bucket"]
    assert "<" not in packet["table_name"]
    assert not str(packet["packet_output_ref"]).startswith("benchmarks/published/")


def test_setup_commands_policy_cleanup_and_env_are_bounded(tmp_path: Path) -> None:
    packet = prepare_northstar_disposable_packet(
        seed="packet-seed",
        bucket="",
        table_name="",
        key="proof/terraform-plan.json",
        region="us-east-1",
        model_id="us.writer.palmyra-x4-v1:0",
        fixture_kind="safe",
        fixture_seed="fixture-seed",
        output_dir=tmp_path,
    )
    setup_commands = (tmp_path / "aws-cli-setup-commands.ps1").read_text(encoding="utf-8")
    cleanup_commands = (tmp_path / "aws-cli-cleanup-commands.ps1").read_text(encoding="utf-8")
    env_template = (tmp_path / "live-run-env.ps1.template").read_text(encoding="utf-8")
    policy = _load(tmp_path / "least-privilege-runtime-policy.json")

    assert "aws s3api create-bucket" in setup_commands
    assert "aws s3api put-public-access-block" in setup_commands
    assert "aws s3api put-object" in setup_commands
    assert "aws dynamodb create-table" in setup_commands
    assert "aws dynamodb wait table-exists" in setup_commands
    assert "aws s3api delete-bucket" not in setup_commands
    assert "aws s3api delete-bucket" in cleanup_commands
    assert "AWS_SECRET_ACCESS_KEY" not in env_template
    assert policy["Statement"][0]["Resource"] == [f"arn:aws:s3:::{packet['bucket']}/{packet['key']}"]
    assert policy["Statement"][1]["Resource"] == [
        "arn:aws:bedrock:us-east-1:<account-id>:inference-profile/us.writer.palmyra-x4-v1:0"
    ]
    assert policy["Statement"][2]["Resource"] == [f"arn:aws:dynamodb:us-east-1:<account-id>:table/{packet['table_name']}"]
