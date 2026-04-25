from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.run_trusted_terraform_plan_decision_runtime_smoke import (
    LiveTerraformReviewConfig,
    execute_trusted_terraform_plan_decision_runtime_smoke,
    main,
)
from scripts.proof.terraform_plan_review_live_support import LiveBedrockSummarizer, is_environment_blocker
from scripts.proof.terraform_plan_review_fixture_support import run_fixture_case


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_smoke_cli_marks_missing_env_as_environment_blocker(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies the provider-backed governed proof command fails closed when live inputs are missing."""
    out = tmp_path / "trusted_terraform_plan_decision_live_runtime.json"
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", raising=False)
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    exit_code = main(["--output", str(out)])
    payload = _load_json(out)

    assert exit_code == 1
    assert payload["observed_result"] == "environment blocker"
    assert payload["execution_status"] == "environment_blocker"
    assert payload["reason"].startswith("missing_required_env:")
    assert isinstance(payload.get("diff_ledger"), list)


def test_runtime_smoke_failure_summary_records_failed_s3_attempt(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies failed provider calls remain visible in blocked live proof output."""

    async def _fake_run_live_review(*, workspace: Path, config: LiveTerraformReviewConfig):
        del workspace, config
        raise RuntimeError("An error occurred (NoSuchBucket) when calling the GetObject operation: missing")

    monkeypatch.setattr(
        "scripts.proof.run_trusted_terraform_plan_decision_runtime_smoke.run_live_review",
        _fake_run_live_review,
    )
    payload = execute_trusted_terraform_plan_decision_runtime_smoke(
        workspace_root=tmp_path / "workspace",
        run_index=1,
        config=LiveTerraformReviewConfig(
            plan_s3_uri="s3://missing-bucket/proof/terraform-plan.json",
            model_id="us.writer.palmyra-x4-v1:0",
            region="us-east-1",
            table_name="TerraformReviewsSmoke_test",
        ),
    )

    assert payload["observed_result"] == "failure"
    assert payload["blocker_taxonomy"] == "missing_object"
    assert payload["provider_interaction_summary"][0]["operation"] == "GetObject"
    assert payload["provider_interaction_summary"][0]["status"] == "attempted"
    assert payload["provider_interaction_summary"][1]["status"] == "not_attempted"


def test_runtime_smoke_wrapper_can_package_live_like_result(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies the runtime-backed wrapper can package a real-service-shaped result into a witness bundle."""

    async def _fake_run_live_review(*, workspace: Path, config: LiveTerraformReviewConfig):
        del config
        result, _case, _s3, _model, publisher = await run_fixture_case(workspace=workspace, case_name="explicit_destroy")
        return result, publisher

    monkeypatch.setattr(
        "scripts.proof.run_trusted_terraform_plan_decision_runtime_smoke.run_live_review",
        _fake_run_live_review,
    )
    payload = execute_trusted_terraform_plan_decision_runtime_smoke(
        workspace_root=tmp_path / "workspace",
        run_index=1,
        config=LiveTerraformReviewConfig(
            plan_s3_uri="s3://terraform-review-fixtures/explicit_destroy.json",
            model_id="anthropic.fake",
            region="us-east-1",
            created_at="2026-03-22T00:00:00Z",
            execution_trace_ref="trusted-terraform-plan-decision-live-runtime",
        ),
    )

    assert payload["observed_result"] == "success"
    assert payload["claim_tier"] == "non_deterministic_lab_only"
    assert payload["publish_decision"] == "normal_publish"
    assert payload["witness_bundle_ref"].endswith("trusted_run_witness_bundle.json")
    assert payload["witness_report"]["observed_result"] == "success"


def test_live_bedrock_summarizer_uses_converse_for_nova_inference_profiles() -> None:
    """Layer: contract. Verifies the advisory Bedrock summary path uses Converse for Amazon Nova inference profiles."""

    class _FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def converse(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(("converse", dict(kwargs)))
            return {
                "output": {"message": {"content": [{"text": "safe to publish"}]}},
                "ResponseMetadata": {"RequestId": "nova-request-123"},
            }

    client = _FakeClient()
    summarizer = LiveBedrockSummarizer(client=client, model_id="us.amazon.nova-lite-v1:0")
    payload = __import__("asyncio").run(
        summarizer.summarize(
            {
                "risk_verdict": "normal_publish",
                "forbidden_operation_hits": [],
                "action_counts": {"create": 1},
            }
        )
    )

    assert client.calls[0][0] == "converse"
    assert client.calls[0][1]["modelId"] == "us.amazon.nova-lite-v1:0"
    assert client.calls[0][1]["messages"][0]["role"] == "user"
    assert payload["summary"] == "safe to publish"
    assert payload["raw_completion_ref"] == "nova-request-123"


def test_live_bedrock_summarizer_uses_converse_for_palmyra_x4() -> None:
    """Layer: contract. Verifies the advisory Bedrock summary path uses Converse for Palmyra X4."""

    class _FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def converse(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(("converse", dict(kwargs)))
            return {
                "output": {"message": {"content": [{"text": "safe to publish"}]}},
                "ResponseMetadata": {"RequestId": "palmyra-request-123"},
            }

    client = _FakeClient()
    summarizer = LiveBedrockSummarizer(client=client, model_id="writer.palmyra-x4-v1:0")
    payload = __import__("asyncio").run(
        summarizer.summarize(
            {
                "risk_verdict": "normal_publish",
                "forbidden_operation_hits": [],
                "action_counts": {"create": 1},
            }
        )
    )

    assert client.calls[0][0] == "converse"
    assert client.calls[0][1]["modelId"] == "writer.palmyra-x4-v1:0"
    assert client.calls[0][1]["messages"][0]["role"] == "user"
    assert payload["summary"] == "safe to publish"
    assert payload["raw_completion_ref"] == "palmyra-request-123"


def test_live_bedrock_summarizer_uses_converse_for_palmyra_x5() -> None:
    """Layer: contract. Verifies the advisory Bedrock summary path uses Converse for Palmyra X5."""

    class _FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def converse(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(("converse", dict(kwargs)))
            return {
                "output": {"message": {"content": [{"text": "safe to publish"}]}},
                "ResponseMetadata": {"RequestId": "palmyra-x5-request-123"},
            }

    client = _FakeClient()
    summarizer = LiveBedrockSummarizer(client=client, model_id="us.writer.palmyra-x5-v1:0")
    payload = __import__("asyncio").run(
        summarizer.summarize(
            {
                "risk_verdict": "normal_publish",
                "forbidden_operation_hits": [],
                "action_counts": {"create": 1},
            }
        )
    )

    assert client.calls[0][0] == "converse"
    assert client.calls[0][1]["modelId"] == "us.writer.palmyra-x5-v1:0"
    assert client.calls[0][1]["messages"][0]["role"] == "user"
    assert payload["summary"] == "safe to publish"
    assert payload["raw_completion_ref"] == "palmyra-x5-request-123"


def test_bedrock_daily_token_throttle_is_treated_as_environment_blocker() -> None:
    """Layer: contract. Verifies Bedrock daily token exhaustion is reported as an environment blocker."""

    ThrottlingException = type("ThrottlingException", (Exception,), {})

    assert is_environment_blocker(ThrottlingException("Too many tokens per day, please wait before trying again."))


def test_runtime_smoke_bedrock_failure_summary_records_prior_s3_attempt(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies Bedrock failures do not erase the preceding S3 read attempt."""

    async def _fake_run_live_review(*, workspace: Path, config: LiveTerraformReviewConfig):
        del workspace, config
        raise RuntimeError("An error occurred (ThrottlingException) when calling the Converse operation: Too many tokens per day")

    monkeypatch.setattr(
        "scripts.proof.run_trusted_terraform_plan_decision_runtime_smoke.run_live_review",
        _fake_run_live_review,
    )
    payload = execute_trusted_terraform_plan_decision_runtime_smoke(
        workspace_root=tmp_path / "workspace",
        run_index=1,
        config=LiveTerraformReviewConfig(
            plan_s3_uri="s3://orket-northstar-test/proof/terraform-plan.json",
            model_id="us.writer.palmyra-x5-v1:0",
            region="us-east-1",
            table_name="TerraformReviewsNorthstar_test",
        ),
    )

    assert payload["observed_result"] == "environment blocker"
    assert payload["provider_interaction_summary"][0]["operation"] == "GetObject"
    assert payload["provider_interaction_summary"][0]["status"] == "attempted"
    assert payload["provider_interaction_summary"][1]["operation"] == "Converse"
    assert payload["provider_interaction_summary"][1]["status"] == "attempted"
    assert payload["provider_interaction_summary"][2]["operation"] == "PutItem"
    assert payload["provider_interaction_summary"][2]["status"] == "not_attempted"
