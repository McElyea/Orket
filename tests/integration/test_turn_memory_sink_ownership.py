"""Layer: integration. A composed turn owns its admitted memory-event sink."""
from __future__ import annotations

import asyncio
import json

import pytest

from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_turn_artifact_destination_ownership import (
    _RUN_A,
    _case,
    _turn_dir,
    _turn_task,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _UnusedMemoryConfig:
    def __init__(self) -> None:
        self.observations: list[str] = []

    def __bool__(self) -> bool:
        self.observations.append("bool")
        raise AssertionError("disabled memory configuration was consumed")

    def __str__(self) -> str:
        self.observations.append("str")
        raise AssertionError("disabled memory configuration was rendered")


async def _read_json(path):
    return json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))


async def _assert_completed_effect(case) -> None:
    run = await case.service.execution_repository.get_run_record(run_id=_RUN_A)
    assert run is not None and run.lifecycle_state.value == "completed"
    assert await case.toolbox.files.read_file("agent_output/out.txt") == "ok"


async def test_composed_turn_keeps_original_memory_sink_after_context_replacement(
    tmp_path, monkeypatch, record_property, deterministic_turn_clock,
) -> None:
    """Layer: integration. Later events and files use the admitted list."""
    case = _case(tmp_path, monkeypatch, deterministic_turn_clock, held_model=True)
    replacement = [{"marker": "replacement"}]

    async with _turn_task(case) as task:
        await asyncio.wait_for(case.owner.entered.wait(), 5)
        case.owner.release.set()
        await asyncio.wait_for(case.model.entered.wait(), 5)
        sink = case.context["_memory_trace_events"]
        assert isinstance(sink, list) and sink is not replacement
        assert [row["interceptor"] for row in sink] == ["before_prompt"]
        case.context["_memory_trace_events"] = replacement
        await responsive_sqlite(tmp_path / "sink-responsive.sqlite3", record_property)
        case.model.release.set()
        result = await asyncio.wait_for(asyncio.shield(task), 15)

    assert result.success is True
    assert case.context["_memory_trace_events"] is replacement
    assert replacement == [{"marker": "replacement"}]
    interceptors = [row["interceptor"] for row in sink]
    assert interceptors == ["before_prompt", "after_model", "before_tool", "after_tool"]
    trace_path = _turn_dir(case) / "memory_trace.json"
    retrieval_path = _turn_dir(case) / "memory_retrieval_trace.json"
    trace = await _read_json(trace_path)
    assert [row["interceptor"] for row in trace["events"]] == interceptors
    assert await asyncio.to_thread(retrieval_path.is_file)
    await _assert_completed_effect(case)


async def test_disabled_composed_turn_does_not_consume_unused_memory_config(
    tmp_path, monkeypatch, record_property, deterministic_turn_clock,
) -> None:
    """Layer: integration. Disabled inputs stay opaque at the public entry."""
    case = _case(tmp_path, monkeypatch, deterministic_turn_clock, held_model=False)
    unused = _UnusedMemoryConfig()
    case.context.update(memory_trace_enabled=False, visibility_mode="")
    for key in ("workflow_id", "memory_snapshot_id", "model_config_id", "policy_set_id", "output_type"):
        case.context[key] = unused

    async with _turn_task(case) as task:
        await asyncio.wait_for(case.owner.entered.wait(), 5)
        assert unused.observations == []
        assert "_memory_trace_events" not in case.context
        await responsive_sqlite(tmp_path / "disabled-responsive.sqlite3", record_property)
        case.owner.release.set()
        result = await asyncio.wait_for(asyncio.shield(task), 15)

    assert result.success is True and unused.observations == []
    assert "_memory_trace_events" not in case.context
    directory = _turn_dir(case)
    assert not await asyncio.to_thread((directory / "memory_trace.json").exists)
    assert not await asyncio.to_thread((directory / "memory_retrieval_trace.json").exists)
    await _assert_completed_effect(case)
