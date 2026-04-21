from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.check_trusted_terraform_live_setup_preflight import (
    build_live_setup_preflight_report,
    main,
)
from scripts.proof.terraform_plan_review_live_support import LiveTerraformReviewConfig


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_setup_preflight_blocks_without_spending_when_required_inputs_missing(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies the setup preflight records missing inputs without provider calls."""
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", raising=False)
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    output = tmp_path / "preflight.json"

    exit_code = main(["--output", str(output)])
    payload = _load(output)

    assert exit_code == 1
    assert payload["observed_result"] == "environment blocker"
    assert payload["provider_calls_executed"] == []
    assert "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI" in payload["missing_env"]
    assert payload["credential_handling"]["credential_values_recorded"] is False
    assert isinstance(payload.get("diff_ledger"), list)


def test_live_setup_preflight_succeeds_for_well_formed_low_cost_inputs() -> None:
    """Layer: contract. Verifies well-formed live setup inputs pass without making AWS calls."""
    report = build_live_setup_preflight_report(
        config=LiveTerraformReviewConfig(
            plan_s3_uri="s3://orket-smoke/terraform/plan.json",
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            region="us-east-1",
            table_name="TerraformReviews",
            created_at="2026-04-19T00:00:00Z",
        )
    )

    assert report["observed_result"] == "success"
    assert report["provider_calls_executed"] == []
    assert report["provider_calls_planned"] == [
        {"service": "s3", "operation": "GetObject", "count": 1, "resource_hint": "s3://orket-smoke/terraform/plan.json"},
        {"service": "bedrock-runtime", "operation": "InvokeModel", "count": 1, "resource_hint": "anthropic.claude-3-haiku-20240307-v1:0"},
        {"service": "dynamodb", "operation": "PutItem", "count": 1, "resource_hint": "TerraformReviews"},
    ]


def test_live_setup_preflight_rejects_invalid_s3_and_unsupported_model() -> None:
    """Layer: contract. Verifies invalid local configuration fails before any provider call."""
    report = build_live_setup_preflight_report(
        config=LiveTerraformReviewConfig(
            plan_s3_uri="https://example.com/plan.json",
            model_id="cohere.fake-model",
            region="us-east-1",
            table_name="TerraformReviews",
        )
    )

    assert report["observed_result"] == "environment blocker"
    assert "invalid_s3_uri" in report["blocking_reasons"]
    assert "unsupported_bedrock_model_for_smoke" in report["blocking_reasons"]


def test_live_setup_preflight_rejects_template_placeholder_s3_uri() -> None:
    """Layer: contract. Verifies setup-packet placeholders cannot pass live preflight."""
    report = build_live_setup_preflight_report(
        config=LiveTerraformReviewConfig(
            plan_s3_uri="s3://<replace-with-globally-unique-smoke-bucket>/proof/plan.json",
            model_id="anthropic.fake-model",
            region="us-east-1",
            table_name="TerraformReviews",
        )
    )

    assert report["observed_result"] == "environment blocker"
    assert "s3_uri_placeholder_not_replaced" in report["blocking_reasons"]
    assert report["provider_calls_executed"] == []


def test_live_setup_preflight_accepts_nova_inference_profile_and_records_converse_operation() -> None:
    """Layer: contract. Verifies the setup preflight admits Nova inference profiles and records Converse truthfully."""
    report = build_live_setup_preflight_report(
        config=LiveTerraformReviewConfig(
            plan_s3_uri="s3://orket-smoke/terraform/plan.json",
            model_id="us.amazon.nova-lite-v1:0",
            region="us-east-1",
            table_name="TerraformReviews",
        )
    )

    assert report["observed_result"] == "success"
    assert report["provider_calls_planned"] == [
        {"service": "s3", "operation": "GetObject", "count": 1, "resource_hint": "s3://orket-smoke/terraform/plan.json"},
        {"service": "bedrock-runtime", "operation": "Converse", "count": 1, "resource_hint": "us.amazon.nova-lite-v1:0"},
        {"service": "dynamodb", "operation": "PutItem", "count": 1, "resource_hint": "TerraformReviews"},
    ]
    assert report["config_summary"]["bedrock_runtime_operation"] == "Converse"
