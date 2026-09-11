# Layer: end-to-end
from __future__ import annotations

import asyncio
import os

import pytest

from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus
from orket.streaming.contracts import StreamEventType
from orket.workloads import run_builtin_workload
from orket.workloads.model_stream_v1 import validate_model_stream_v1_start
from scripts.odr.model_runtime_control import complete_with_transient_provider
from scripts.odr.run_odr_7b_baseline import _resolve_role_base_url as baseline_base_url
from scripts.odr.run_odr_single_vs_coordinated import _resolve_role_base_url as comparison_base_url

pytestmark = [pytest.mark.end_to_end, pytest.mark.skipif(
    os.getenv("ORKET_RUN_LIVE_AGENT_LLAMA_CPP") != "1", reason="requires live llama.cpp")]


@pytest.mark.asyncio
async def test_llama_cpp_builtin_stream_reaches_committed_terminal_state(tmp_path, monkeypatch) -> None:
    """Layer: end-to-end. Real SSE generation crosses workload validation, events and commit."""
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "llama_cpp")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", os.environ["ORKET_GOVERNED_AGENT_MODEL"])
    monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "true")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_TIMEOUT_S", "60")
    validate_model_stream_v1_start(input_config={}, turn_params={})
    manager = InteractionManager(bus=StreamBus(), commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
                                 project_root=tmp_path)
    session = await manager.start({})
    queue = await manager.subscribe(session)
    turn = await manager.begin_turn(session, {}, {})
    context = await manager.create_context(session, turn)
    await asyncio.wait_for(run_builtin_workload(workload_id="model_stream_v1",
        input_config={"prompt": "Reply with OK.", "max_tokens": 32}, turn_params={},
        interaction_context=context), timeout=90)
    await manager.finalize(session, turn)
    events = []
    while not events or events[-1].event_type != StreamEventType.COMMIT_FINAL:
        events.append(await asyncio.wait_for(queue.get(), timeout=10))
    assert any(event.event_type == StreamEventType.TOKEN_DELTA for event in events)
    assert any(event.event_type == StreamEventType.TURN_FINAL for event in events)
    assert events[-1].payload["commit_outcome"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("resolve", [baseline_base_url, comparison_base_url])
async def test_llama_cpp_odr_transient_generation(resolve, monkeypatch) -> None:
    """Layer: end-to-end. Each ODR entrypoint's endpoint resolution reaches real inference."""
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    response, latency, release = await complete_with_transient_provider(
        model=os.environ["ORKET_GOVERNED_AGENT_MODEL"], messages=[{"role": "user", "content": "Reply with OK."}],
        temperature=0, timeout=60, provider_name="llama_cpp", base_url=resolve(provider="llama_cpp", raw=""))
    assert response.content.strip()
    assert response.raw["input_tokens"] > 0 and response.raw["output_tokens"] > 0
    assert latency > 0
    assert release["provider"] == "llama_cpp" and release["status"] == "operator_managed"
    assert release["unload_attempted"] is False
