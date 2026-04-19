from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.run_trusted_terraform_plan_decision_runtime_smoke import (
    LiveTerraformReviewConfig,
    execute_trusted_terraform_plan_decision_runtime_smoke,
    main,
)
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
