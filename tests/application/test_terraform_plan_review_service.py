from __future__ import annotations

from pathlib import Path

import pytest

from tests.application.terraform_plan_review_support import load_fixture_manifest, run_fixture_case


@pytest.mark.integration
@pytest.mark.parametrize("case_name", list(load_fixture_manifest().keys()))
async def test_terraform_plan_review_fixtures_follow_locked_outcomes(tmp_path: Path, case_name: str) -> None:
    """Layer: integration. Verifies the local governed harness follows the locked fixture corpus outcomes."""
    result, case, _s3, _model, publisher = await run_fixture_case(tmp_path=tmp_path, case_name=case_name)
    assert result.governance_artifact.publish_decision == case.expected_publish_decision
    assert result.governance_artifact.summary_status == case.expected_summary_status
    assert result.governance_artifact.final_verdict_source == case.expected_final_verdict_source
    assert result.governance_artifact.deterministic_analysis_complete == case.expected_deterministic_analysis_complete
    assert result.deterministic_analysis.action_counts == case.expected_action_counts
    assert result.final_review.risk_verdict == case.expected_verdict
    assert Path(result.artifact_bundle.artifact_paths["input_artifact"]).is_file()
    assert Path(result.artifact_bundle.artifact_paths["deterministic_analysis"]).is_file()
    assert Path(result.artifact_bundle.artifact_paths["model_summary"]).is_file()
    assert Path(result.artifact_bundle.artifact_paths["final_review"]).is_file()
    assert Path(result.artifact_bundle.artifact_paths["governance_artifact"]).is_file()
    if case.expected_publish_decision == "no_publish":
        assert publisher.calls == []
    else:
        assert len(publisher.calls) == 1


@pytest.mark.integration
async def test_model_failure_degrades_publish_after_deterministic_success(tmp_path: Path) -> None:
    """Layer: integration. Verifies Bedrock failure degrades publication without changing deterministic verdict authority."""
    result, _case, _s3, _model, publisher = await run_fixture_case(
        tmp_path=tmp_path,
        case_name="create_update_only",
        model_error=RuntimeError("bedrock_down"),
    )
    assert result.governance_artifact.execution_status == "degraded"
    assert result.governance_artifact.publish_decision == "degraded_publish"
    assert result.governance_artifact.observed_result_classification == "partial success"
    assert result.model_summary.summary_status == "summary_unavailable"
    assert result.final_review.summary_status == "summary_unavailable"
    assert result.governance_artifact.final_verdict_source == "deterministic_analysis"
    assert len(publisher.calls) == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("capability", "expected_mutation_attempt"),
    [
        ("shell_execution", False),
        ("local_file_mutation", True),
        ("unapproved_network_call", False),
        ("prohibited_mutation", True),
    ],
)
async def test_policy_blocked_capabilities_are_not_runtime_failures(
    tmp_path: Path,
    capability: str,
    expected_mutation_attempt: bool,
) -> None:
    """Layer: integration. Verifies policy-blocked probes preserve blocked-by-policy semantics instead of runtime failure."""
    result, _case, _s3, _model, publisher = await run_fixture_case(
        tmp_path=tmp_path,
        case_name="create_update_only",
        prohibited_capability_attempt=capability,
    )
    assert result.governance_artifact.execution_status == "blocked_by_policy"
    assert result.governance_artifact.publish_decision == "no_publish"
    assert result.governance_artifact.blocked_capability == capability
    assert result.governance_artifact.policy_violation_type == "capability_blocked"
    assert result.governance_artifact.observed_result_classification == "failure"
    assert publisher.calls == []
    if expected_mutation_attempt:
        assert capability in result.governance_artifact.durable_mutations_attempted
    else:
        assert capability not in result.governance_artifact.durable_mutations_attempted


@pytest.mark.integration
async def test_model_override_conflict_is_preserved_without_changing_verdict_authority(tmp_path: Path) -> None:
    """Layer: integration. Verifies conflicting model output stays advisory and cannot override deterministic verdicts."""
    result, _case, _s3, _model, publisher = await run_fixture_case(
        tmp_path=tmp_path,
        case_name="explicit_destroy",
        model_payload={
            "summary": "No risky operations detected.",
            "review_focus_areas": ["Validate human expectations."],
            "suggested_verdict": "safe_for_v1_policy",
            "raw_completion_ref": "fake:model:conflict",
        },
    )
    assert result.final_review.risk_verdict == "risky_for_v1_policy"
    assert result.model_summary.summary == "No risky operations detected."
    assert "model_verdict_conflict" in result.model_summary.advisory_errors
    assert result.governance_artifact.final_verdict_source == "deterministic_analysis"
    assert len(publisher.calls) == 1
