from __future__ import annotations

from pathlib import Path

import pytest

from orket.reforger.proof_slices import phase0_adapt_request, phase0_baseline_request
from orket.reforger.service import PromptReforgerService


@pytest.mark.integration
def test_phase0_baseline_service_run_records_structural_blocked_live_proof(tmp_path: Path) -> None:
    service = PromptReforgerService(
        work_root=tmp_path / "work",
        artifact_root=tmp_path / "artifacts",
    )

    execution = service.execute(phase0_baseline_request())
    artifact = service.read_service_run(execution.result.service_run_id)

    assert execution.result.result_class == "unsupported"
    assert execution.result.observed_path == "primary"
    assert execution.result.observed_result == "failure"
    assert execution.result.candidate_summary.evaluated_candidate_count == 0
    assert execution.result.bundle_ref is None
    assert execution.run_artifact_path.name == "reforger_service_run_phase0-baseline-run-0001.json"
    assert execution.scoreboard_artifact_path.is_file()
    assert artifact["verification"]["proof_type"] == "structural"
    assert artifact["verification"]["live_proof"]["observed_path"] == "blocked"
    assert artifact["verification"]["live_proof"]["observed_result"] == "environment blocker"
    assert "qualifying_bundle" not in artifact


@pytest.mark.integration
def test_phase0_adapt_service_run_freezes_qualifying_bundle_and_verdict_source(tmp_path: Path) -> None:
    service = PromptReforgerService(
        work_root=tmp_path / "work",
        artifact_root=tmp_path / "artifacts",
    )

    execution = service.execute(phase0_adapt_request())
    artifact = service.read_service_run(execution.result.service_run_id)

    assert execution.result.result_class == "certified_with_limits"
    assert execution.result.observed_result == "success"
    assert execution.result.candidate_summary.evaluated_candidate_count == 4
    assert execution.result.candidate_summary.winning_candidate_id == "0003"
    assert execution.result.candidate_summary.winning_score == pytest.approx(0.9)
    assert execution.result.bundle_ref.endswith("reforger_service_run_phase0-adapt-run-0007.json")
    assert execution.run_artifact_path.name == "reforger_service_run_phase0-adapt-run-0007.json"
    assert execution.scoreboard_artifact_path.name == "reforger_service_run_phase0-adapt-run-0007_scoreboard.json"
    assert artifact["external_consumer_verdict"]["verdict_source"] == "service_adopted"
    assert artifact["external_consumer_verdict"]["verdict_class"] == "certified_with_limits"
    assert artifact["qualifying_bundle"]["scorecard_ref"].endswith(
        "reforger_service_run_phase0-adapt-run-0007_scoreboard.json"
    )
    assert artifact["qualifying_bundle"]["target_runtime_identity"]["model_id"] == "fake"
    assert artifact["candidate_records"][2]["candidate_id"] == "0003"
    assert artifact["candidate_records"][2]["score"] == pytest.approx(0.9)


@pytest.mark.integration
def test_execute_payload_returns_result_envelope(tmp_path: Path) -> None:
    service = PromptReforgerService(
        work_root=tmp_path / "work",
        artifact_root=tmp_path / "artifacts",
    )

    payload = service.execute_payload(phase0_adapt_request().to_payload())

    assert payload["request_id"] == "phase0-adapt-textmystery-v0"
    assert payload["service_run_id"] == "phase0-adapt-run-0007"
    assert payload["result_class"] == "certified_with_limits"
