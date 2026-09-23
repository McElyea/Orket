"""Integration counterexample and acceptance for run-level Packet-1 capture.

Fixture assumptions:
- ``ledger_pipeline`` opens the real ``ExecutionPipeline`` and closes every owner.
- The controlled execution replaces only model work; run start, finalization,
  physical summary publication, and the SQLite run ledger remain production paths.
- Completion uses the established acceptance helper so the run can finish normally.
- Start, final, physical, and telemetry observations are retained before assertions.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import ledger_pipeline_fixture
from tests.integration.packet1_input_support import (
    CONTROLLED_TELEMETRY,
    ENVIRONMENT_A,
    ENVIRONMENT_B,
    ENVIRONMENT_C,
    run_controlled_packet1,
    set_packet1_environment,
    write_epic_assets,
)

pytestmark = pytest.mark.integration
_pipeline = ledger_pipeline_fixture.ledger_pipeline


def _assert_captured_intent(packet1_facts: dict, *, expected_profile: str) -> None:
    assert packet1_facts["intended_provider"] == ENVIRONMENT_A["ORKET_LLM_PROVIDER"]
    assert packet1_facts["intended_profile"] == expected_profile


def _assert_telemetry_precedence(provenance: dict) -> None:
    assert provenance["actual_provider"] == CONTROLLED_TELEMETRY["provider_backend"]
    assert provenance["actual_model"] == CONTROLLED_TELEMETRY["model"]
    assert provenance["actual_profile"] == CONTROLLED_TELEMETRY["profile_id"]
    assert provenance["fallback_occurred"] is True
    assert provenance["execution_profile"] == "fallback"


def _record_observation(
    record_property,
    *,
    started_packet1: dict,
    summary: dict,
    physical_summary: dict,
    summary_path: Path,
) -> tuple[dict, dict]:
    provenance = summary["truthful_runtime_packet1"]["provenance"]
    physical_provenance = physical_summary["truthful_runtime_packet1"]["provenance"]
    record_property(
        "packet1_input_observation",
        json.dumps(
            {
                "start_intent": {
                    "provider": started_packet1.get("intended_provider"),
                    "profile": started_packet1.get("intended_profile"),
                },
                "final_intent": {
                    "provider": provenance.get("intended_provider"),
                    "profile": provenance.get("intended_profile"),
                },
                "final_telemetry": {
                    key: provenance.get(key)
                    for key in (
                        "actual_provider",
                        "actual_model",
                        "actual_profile",
                        "fallback_occurred",
                        "execution_profile",
                    )
                },
                "physical_intent": {
                    "provider": physical_provenance.get("intended_provider"),
                    "profile": physical_provenance.get("intended_profile"),
                },
                "physical_matches_ledger": physical_summary == summary,
                "summary_path": str(summary_path),
            },
            sort_keys=True,
        ),
    )
    return provenance, physical_provenance


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ambient_drift",
    [pytest.param(False, id="unchanged-environment-control"), pytest.param(True, id="ambient-b-c-drift")],
)
async def test_run_packet1_intent_uses_runtime_construction_inputs(
    _pipeline,
    test_root: Path,
    workspace: Path,
    db_path: str,
    monkeypatch: pytest.MonkeyPatch,
    record_property,
    ambient_drift: bool,
) -> None:
    epic_id = f"packet1_inputs_{'drift' if ambient_drift else 'control'}"
    run_id = f"sess-{epic_id}"
    await write_epic_assets(test_root, epic_id)
    set_packet1_environment(monkeypatch, ENVIRONMENT_A)
    pipeline = await _pipeline(test_root, workspace, db_path)
    assert dict(pipeline.runtime_context.construction_inputs.environment)["ORKET_LLM_PROVIDER"] == "llama_cpp"

    if ambient_drift:
        set_packet1_environment(monkeypatch, ENVIRONMENT_B)

    def after_start() -> None:
        if ambient_drift:
            set_packet1_environment(monkeypatch, ENVIRONMENT_C)

    observation = await run_controlled_packet1(
        pipeline,
        monkeypatch,
        workspace=workspace,
        epic_id=epic_id,
        run_id=run_id,
        telemetry=CONTROLLED_TELEMETRY,
        after_start=after_start,
    )
    started_packet1 = observation["started"]
    ledger = observation["ledger"]
    summary = observation["summary"]
    physical_summary = observation["physical"]
    provenance, physical_provenance = _record_observation(
        record_property,
        started_packet1=started_packet1,
        summary=summary,
        physical_summary=physical_summary,
        summary_path=observation["summary_path"],
    )

    assert ledger["status"] == "done"
    assert physical_summary == summary
    # Before telemetry, fallback has not been observed and the existing profile is default.
    _assert_captured_intent(started_packet1, expected_profile="default")
    expected_profile = ENVIRONMENT_A["ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID"]
    _assert_captured_intent(provenance, expected_profile=expected_profile)
    _assert_telemetry_precedence(provenance)
    _assert_captured_intent(physical_provenance, expected_profile=expected_profile)
