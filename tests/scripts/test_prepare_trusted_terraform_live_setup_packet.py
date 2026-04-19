from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.prepare_trusted_terraform_live_setup_packet import (
    SETUP_PACKET_SCHEMA_VERSION,
    main,
    prepare_setup_packet,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_setup_packet_cli_writes_no_spend_template_packet(tmp_path: Path) -> None:
    """Layer: contract. Verifies setup-packet generation writes local files without provider calls."""
    packet_root = tmp_path / "packet"
    output = tmp_path / "setup-packet.json"

    exit_code = main(["--packet-root", str(packet_root), "--output", str(output)])
    payload = _load(output)

    assert exit_code == 0
    assert payload["schema_version"] == SETUP_PACKET_SCHEMA_VERSION
    assert payload["observed_result"] == "success"
    assert payload["provider_calls_executed"] == []
    assert payload["live_execution_ready"] is False
    assert payload["live_execution_blockers"] == ["bucket_placeholder_not_replaced"]
    assert "credentials_written_to_packet" in payload["credential_handling"]
    assert payload["credential_handling"]["credentials_written_to_packet"] is False
    assert isinstance(payload.get("diff_ledger"), list)

    expected_files = {
        "terraform-plan-safe-smoke.plan.json",
        "live-run.env.template",
        "live-run-env.ps1.template",
        "aws-cli-setup-commands.ps1",
        "aws-cli-cleanup-commands.ps1",
        "least-privilege-runtime-policy.json",
        "live-run-checklist.md",
    }
    assert {path.name for path in packet_root.iterdir()} == expected_files
    assert _load(packet_root / "terraform-plan-safe-smoke.plan.json")["resource_changes"]


def test_setup_packet_with_real_resource_names_is_live_ready_but_not_proof(tmp_path: Path) -> None:
    """Layer: contract. Verifies concrete resource names produce a ready setup packet without AWS calls."""
    packet_root = tmp_path / "packet"
    payload = prepare_setup_packet(
        packet_root=packet_root,
        plan_fixture=Path("tests/fixtures/terraform_plan_reviewer_v1/create_update_only.plan.json"),
        bucket="orket-smoke-proof-bucket-123456",
        key="proof/terraform-plan.json",
        region="us-west-2",
        model_id="anthropic.fake-model",
        table_name="TerraformReviewsSmoke",
        created_at="2026-04-19T00:00:00Z",
        execution_trace_ref="trusted-terraform-plan-decision-live-runtime",
        policy_bundle_id="terraform_plan_reviewer_v1",
    )

    env_template = (packet_root / "live-run.env.template").read_text(encoding="utf-8")
    setup_commands = (packet_root / "aws-cli-setup-commands.ps1").read_text(encoding="utf-8")
    policy = _load(packet_root / "least-privilege-runtime-policy.json")

    assert payload["live_execution_ready"] is True
    assert payload["provider_calls_executed"] == []
    assert payload["s3_plan_uri"] == "s3://orket-smoke-proof-bucket-123456/proof/terraform-plan.json"
    assert "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI=s3://orket-smoke-proof-bucket-123456/proof/terraform-plan.json" in env_template
    assert "AWS_ACCESS_KEY" not in env_template
    assert "aws s3api create-bucket" in setup_commands
    assert policy["Statement"][0]["Action"] == ["s3:GetObject"]
    assert policy["Statement"][2]["Action"] == ["dynamodb:PutItem"]


def test_setup_packet_flags_non_anthropic_model_before_live_execution(tmp_path: Path) -> None:
    """Layer: contract. Verifies unsupported model ids stay visible as live-execution blockers."""
    payload = prepare_setup_packet(
        packet_root=tmp_path / "packet",
        plan_fixture=Path("tests/fixtures/terraform_plan_reviewer_v1/create_update_only.plan.json"),
        bucket="orket-smoke-proof-bucket-123456",
        key="proof/terraform-plan.json",
        region="us-west-2",
        model_id="cohere.fake-model",
        table_name="TerraformReviewsSmoke",
        created_at="2026-04-19T00:00:00Z",
        execution_trace_ref="trusted-terraform-plan-decision-live-runtime",
        policy_bundle_id="terraform_plan_reviewer_v1",
    )

    assert payload["live_execution_ready"] is False
    assert payload["live_execution_blockers"] == ["unsupported_bedrock_model_for_smoke"]
