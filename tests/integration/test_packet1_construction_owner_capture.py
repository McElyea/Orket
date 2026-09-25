"""Matched controls for the construction owner used by Packet-1 closeout.

The model workload is controlled. Pipeline construction, epic ownership, cards,
run ledger, closeout, physical publication, and interruption behavior are real.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import ledger_pipeline_fixture
from tests.helpers.card_completion import complete_existing_card
from tests.helpers.epic_closeout_ownership import (
    assert_interrupted,
    assert_owned,
    complete_held_operation,
    hold_sync,
    interrupt_observation,
    physical,
    record_json,
)
from tests.integration.packet1_input_support import (
    CONTROLLED_TELEMETRY,
    ENVIRONMENT_A,
    ENVIRONMENT_B,
    read_json,
    set_packet1_environment,
    write_epic_assets,
    write_json,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_pipeline = ledger_pipeline_fixture.ledger_pipeline


def _replacement_inputs(inputs: Any):
    return replace(inputs, environment={**dict(inputs.environment), **ENVIRONMENT_B})


def _install_controlled_model(pipeline, monkeypatch, *, workspace: Path, run_id: str) -> dict[str, Any]:
    started: dict[str, Any] = {}

    async def execute_controlled_model(**kwargs: Any) -> None:
        row = await pipeline.run_ledger.get_run(str(kwargs["run_id"]))
        assert row is not None
        started.update(row["artifact_json"]["packet1_facts"])
        await write_json(
            workspace / "observability" / run_id / "ISSUE-1/001_lead_architect/model_response_raw.json",
            CONTROLLED_TELEMETRY,
        )
        await complete_existing_card(
            pipeline.async_cards,
            "ISSUE-1",
            workspace,
            service=pipeline.runtime_context.card_completion,
        )

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_controlled_model)
    return started


def _packet1_observation(started: dict[str, Any], ledger: dict[str, Any], physical_summary: dict) -> dict:
    summary = ledger["summary_json"]
    final = summary["truthful_runtime_packet1"]["provenance"]
    physical_final = physical_summary["truthful_runtime_packet1"]["provenance"]
    fields = ("intended_provider", "intended_profile", "actual_provider", "actual_model", "actual_profile")
    return {
        "start": {key: started.get(key) for key in fields},
        "final": {key: final.get(key) for key in fields},
        "physical": {key: physical_final.get(key) for key in fields},
        "physical_matches_ledger": physical_summary == summary,
        "ledger_status": ledger.get("status"),
    }


def _assert_packet1_a(observation: dict[str, Any]) -> None:
    assert observation["start"]["intended_provider"] == ENVIRONMENT_A["ORKET_LLM_PROVIDER"]
    assert observation["start"]["intended_profile"] == "default"
    expected_profile = ENVIRONMENT_A["ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID"]
    for phase in ("final", "physical"):
        assert observation[phase]["intended_provider"] == ENVIRONMENT_A["ORKET_LLM_PROVIDER"]
        assert observation[phase]["intended_profile"] == expected_profile
        assert observation[phase]["actual_provider"] == CONTROLLED_TELEMETRY["provider_backend"]
        assert observation[phase]["actual_model"] == CONTROLLED_TELEMETRY["model"]
        assert observation[phase]["actual_profile"] == CONTROLLED_TELEMETRY["profile_id"]
    assert observation["physical_matches_ledger"] is True and observation["ledger_status"] == "done"


@pytest.mark.parametrize("mutate", [False, True], ids=["unchanged", "context-owner-a-to-b"])
# Layer: integration
async def test_packet1_closeout_retains_constructed_input_owner(
    _pipeline, test_root, workspace, db_path, tmp_path, monkeypatch, record_property, mutate,
) -> None:
    epic_id = f"packet1_owner_{'mutated' if mutate else 'healthy'}"
    run_id = f"session-{epic_id}"
    await write_epic_assets(test_root, epic_id)
    set_packet1_environment(monkeypatch, ENVIRONMENT_A)
    pipeline = await _pipeline(test_root, workspace, db_path)
    inputs_a = pipeline.runtime_context.construction_inputs
    assert inputs_a is not None
    inputs_b = _replacement_inputs(inputs_a)
    started = _install_controlled_model(
        pipeline, monkeypatch, workspace=workspace, run_id=run_id)
    telemetry_path = workspace / "observability" / run_id / "ISSUE-1/001_lead_architect/model_response_raw.json"
    summary_path = workspace / "runs" / run_id / "run_summary.json"
    hold = hold_sync(monkeypatch, pipeline, "_packet1_model_response_paths_at")
    task = asyncio.create_task(pipeline.run_epic(epic_id, build_id=f"build-{epic_id}", session_id=run_id))
    held: dict[str, Any] = {}

    def mutate_owner() -> None:
        if mutate:
            pipeline.runtime_context.construction_inputs = inputs_b
        held.update({
            "selected_is_a": pipeline.runtime_context.construction_inputs is inputs_a,
            "selected_is_b": pipeline.runtime_context.construction_inputs is inputs_b,
        })

    try:
        ownership, _ = await complete_held_operation(
            task=task,
            hold=hold,
            sqlite_path=tmp_path / "responsive.sqlite3",
            record_property=record_property,
            paths=(telemetry_path, summary_path),
            mutate=mutate_owner,
        )
    finally:
        pipeline.runtime_context.construction_inputs = inputs_a
        hold.release.set()
    ledger = await pipeline.run_ledger.get_run(run_id)
    assert ledger is not None
    physical_summary = await read_json(summary_path)
    observation = {
        "ownership": ownership,
        "held": held,
        "packet1": _packet1_observation(started, ledger, physical_summary),
        "summary_physical": await physical(summary_path),
        "telemetry_physical": await physical(telemetry_path),
    }
    record_json(record_property, "packet1_construction_owner_observation", observation)
    assert ownership["active_during_sqlite"] is True and ownership["expired"] is False
    assert ownership["worker_thread"] != ownership["loop_thread"]
    assert ownership["finished_after_release"] is True
    assert held["selected_is_b" if mutate else "selected_is_a"] is True
    assert observation["summary_physical"]["is_file"] and observation["telemetry_physical"]["is_file"]
    _assert_packet1_a(observation["packet1"])


# Layer: integration
async def test_packet1_closeout_cancellation_does_not_publish_later_summary(
    _pipeline, test_root, workspace, db_path, tmp_path, monkeypatch, record_property,
) -> None:
    epic_id, run_id = "packet1_owner_cancel", "session-packet1-owner-cancel"
    await write_epic_assets(test_root, epic_id)
    set_packet1_environment(monkeypatch, ENVIRONMENT_A)
    pipeline = await _pipeline(test_root, workspace, db_path)
    inputs_a = pipeline.runtime_context.construction_inputs
    assert inputs_a is not None
    inputs_b = _replacement_inputs(inputs_a)
    started = _install_controlled_model(
        pipeline, monkeypatch, workspace=workspace, run_id=run_id)
    telemetry_path = workspace / "observability" / run_id / "ISSUE-1/001_lead_architect/model_response_raw.json"
    summary_path = workspace / "runs" / run_id / "run_summary.json"
    hold = hold_sync(monkeypatch, pipeline, "_packet1_model_response_paths_at")
    task = asyncio.create_task(pipeline.run_epic(epic_id, build_id=f"build-{epic_id}", session_id=run_id))
    try:
        observation = await interrupt_observation(
            task=task,
            hold=hold,
            timed=False,
            sqlite_path=tmp_path / "responsive.sqlite3",
            record_property=record_property,
            paths=(telemetry_path, summary_path),
            mutate=lambda: setattr(pipeline.runtime_context, "construction_inputs", inputs_b),
            extra=lambda: {
                "selected_is_b": pipeline.runtime_context.construction_inputs is inputs_b,
                "start": dict(started),
            },
        )
    finally:
        pipeline.runtime_context.construction_inputs = inputs_a
        hold.release.set()
    ledger = await pipeline.run_ledger.get_run(run_id)
    observation.update({
        "ledger": ledger,
        "summary_physical": await physical(summary_path),
        "telemetry_physical": await physical(telemetry_path),
    })
    record_json(record_property, "packet1_construction_owner_cancel_observation", observation)
    assert_owned(observation)
    assert_interrupted(observation, timed=False)
    assert observation["pre_release"]["extra"]["selected_is_b"] is True
    assert observation["pre_release"]["extra"]["start"]["intended_provider"] == (
        ENVIRONMENT_A["ORKET_LLM_PROVIDER"]
    )
    assert observation["telemetry_physical"]["is_file"] is True
    assert observation["summary_physical"]["exists"] is False
