from __future__ import annotations

# Layer: integration
import asyncio

import pytest

from orket.runtime.provider_runtime_target import ProviderRuntimeTarget
from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus, StreamBusConfig
from orket.streaming.contracts import StreamEventType
from orket.streaming.model_provider import ModelStreamProvider, ProviderEvent, ProviderEventType, ProviderTurnRequest
from orket.workloads import run_builtin_workload


async def _drain_until_commit(queue: asyncio.Queue):
    events = []
    while True:
        event = await queue.get()
        events.append(event)
        if event.event_type == StreamEventType.COMMIT_FINAL:
            return events


@pytest.mark.asyncio
async def test_stream_test_spam_deltas_emits_drop_ranges_and_commit_ok(tmp_path):
    manager = InteractionManager(
        bus=StreamBus(
            StreamBusConfig(
                best_effort_max_events_per_turn=8,
                bounded_max_events_per_turn=32,
                max_bytes_per_turn_queue=10_000,
            )
        ),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 7}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    await run_builtin_workload(
        workload_id="stream_test_v1",
        input_config={"mode": "spam_deltas", "seed": 7, "delta_count": 80, "chunk_size": 2},
        turn_params={},
        interaction_context=context,
    )
    await manager.finalize(session_id, turn_id)
    events = await _drain_until_commit(queue)

    turn_final = next(event for event in events if event.event_type == StreamEventType.TURN_FINAL)
    assert "dropped_seq_ranges" in turn_final.payload
    commit_final = next(event for event in events if event.event_type == StreamEventType.COMMIT_FINAL)
    assert commit_final.payload["commit_outcome"] == "ok"


@pytest.mark.asyncio
async def test_stream_test_finalize_then_wait_cancel_after_final_is_noop(tmp_path):
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 9}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    hints = await run_builtin_workload(
        workload_id="stream_test_v1",
        input_config={"mode": "finalize_then_wait", "seed": 9, "wait_ms": 40},
        turn_params={},
        interaction_context=context,
    )
    await manager.finalize(session_id, turn_id)

    buffered = []
    while True:
        event = await queue.get()
        buffered.append(event)
        if event.event_type == StreamEventType.TURN_FINAL:
            break

    await manager.cancel(turn_id)
    if hints.get("post_finalize_wait_ms", 0) > 0:
        await asyncio.sleep(int(hints["post_finalize_wait_ms"]) / 1000.0)
    buffered.extend(await _drain_until_commit(queue))

    terminal_events = [event for event in buffered if event.event_type in {StreamEventType.TURN_FINAL, StreamEventType.TURN_INTERRUPTED}]
    assert len(terminal_events) == 1
    assert terminal_events[0].event_type == StreamEventType.TURN_FINAL
    assert all(event.event_type != StreamEventType.TURN_INTERRUPTED for event in buffered)


@pytest.mark.asyncio
async def test_model_stream_v1_stub_path_commits_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "stub")
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 5}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    await run_builtin_workload(
        workload_id="model_stream_v1",
        input_config={"seed": 5, "mode": "basic"},
        turn_params={},
        interaction_context=context,
    )
    await manager.finalize(session_id, turn_id)
    events = await _drain_until_commit(queue)

    event_types = [event.event_type for event in events]
    assert StreamEventType.MODEL_SELECTED in event_types
    assert StreamEventType.MODEL_LOADING in event_types
    assert StreamEventType.MODEL_READY in event_types
    assert StreamEventType.TOKEN_DELTA in event_types
    commit_final = next(event for event in events if event.event_type == StreamEventType.COMMIT_FINAL)
    assert commit_final.payload["commit_outcome"] == "ok"


@pytest.mark.asyncio
async def test_model_stream_v1_stub_cancel_before_first_token_interrupts(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "stub")
    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 5}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    task = asyncio.create_task(
        run_builtin_workload(
            workload_id="model_stream_v1",
            input_config={"seed": 5, "mode": "basic", "first_token_delay_ms": 100},
            turn_params={},
            interaction_context=context,
        )
    )

    seen = []
    while True:
        event = await queue.get()
        seen.append(event)
        if event.event_type == StreamEventType.MODEL_LOADING:
            await manager.cancel(turn_id)
            break

    await task
    await manager.finalize(session_id, turn_id)
    seen.extend(await _drain_until_commit(queue))

    terminal_events = [event for event in seen if event.event_type in {StreamEventType.TURN_FINAL, StreamEventType.TURN_INTERRUPTED}]
    assert len(terminal_events) == 1
    assert terminal_events[0].event_type == StreamEventType.TURN_INTERRUPTED
    assert all(event.event_type != StreamEventType.TURN_FINAL for event in seen)


@pytest.mark.asyncio
async def test_model_stream_v1_real_path_uses_shared_runtime_target(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "lmstudio")
    resolve_calls: list[dict[str, object]] = []

    async def _fake_resolve(**kwargs):
        resolve_calls.append(dict(kwargs))
        return ProviderRuntimeTarget(
            requested_provider="lmstudio",
            canonical_provider="openai_compat",
            requested_model="qwen3.5-coder",
            model_id="qwen3.5-4b",
            base_url="http://127.0.0.1:1234/v1",
            resolution_mode="auto_selected_from_disk",
            inventory_source="lms_cli",
            available_models=("qwen3.5-0.8b", "qwen3.5-4b"),
            loaded_models_before=(),
            loaded_models_after=("qwen3.5-4b",),
            auto_load_attempted=True,
            auto_load_performed=True,
            status="OK",
        )

    class _FakeOpenAIProvider(ModelStreamProvider):
        def __init__(self, *, model_id: str, base_url: str, api_key=None, timeout_s: float = 60.0) -> None:
            self.model_id = model_id
            self.base_url = base_url
            self.timeout_s = timeout_s

        async def start_turn(self, req: ProviderTurnRequest):
            _ = req
            provider_turn_id = "provider-turn-shared-target"
            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.SELECTED,
                payload={"model_id": self.model_id},
            )
            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.LOADING,
                payload={"cold_start": False},
            )
            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.READY,
                payload={"model_id": self.model_id},
            )
            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.TOKEN_DELTA,
                payload={"delta": "ok", "index": 0},
            )
            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.STOPPED,
                payload={"stop_reason": "completed"},
            )

        async def cancel(self, provider_turn_id: str) -> None:
            _ = provider_turn_id

    monkeypatch.setattr("orket.workloads.model_stream_v1.resolve_provider_runtime_target", _fake_resolve)
    monkeypatch.setattr("orket.workloads.model_stream_v1.OpenAICompatModelStreamProvider", _FakeOpenAIProvider)

    manager = InteractionManager(
        bus=StreamBus(),
        commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
        project_root=tmp_path,
    )
    session_id = await manager.start({})
    queue = await manager.subscribe(session_id)
    turn_id = await manager.begin_turn(session_id, {"seed": 5}, {})
    context = await manager.create_context(session_id, turn_id)
    await queue.get()  # turn_accepted

    await run_builtin_workload(
        workload_id="model_stream_v1",
        input_config={"model_id": "qwen3.5-coder"},
        turn_params={},
        interaction_context=context,
    )
    await manager.finalize(session_id, turn_id)
    events = await _drain_until_commit(queue)

    assert resolve_calls[0]["provider"] == "lmstudio"
    assert any(event.event_type == StreamEventType.MODEL_SELECTED for event in events)
    assert any(
        event.event_type == StreamEventType.TOKEN_DELTA and event.payload.get("delta") == "ok"
        for event in events
    )
