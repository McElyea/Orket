"""Isolated public builtin workload, real catalogs/completions and durable interaction commit."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from functools import partial
from pathlib import Path

import psutil
import pytest

import orket
from orket.adapters.execution import owned_io
from orket.application.interactions.commit import CommitOrchestrator
from orket.application.interactions.manager import InteractionManager
from orket.core.contracts.interaction_stream import StreamEventType
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging
from orket.streaming import StreamBus
from orket.workloads import model_stream_v1 as workload
from orket.workloads import run_builtin_workload
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.model_stream_input_controls import (
    configure,
    input_values,
    install_observers,
    mutate,
    response,
    seed_roots,
    snapshot_inputs,
)
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.sdk_observation_controls import public_caller


async def complete_interaction(manager, session_id, turn_id, queue, result, root):
    if isinstance(result, BaseException) or result.get("request_cancel_turn", 0):
        await manager.cancel(turn_id)
    await manager.finalize(session_id, turn_id)
    events = []
    async with asyncio.timeout(5):
        while True:
            event = await queue.get()
            events.append(event.model_dump(mode="json"))
            if event.event_type == StreamEventType.COMMIT_FINAL:
                break
    path = root / "workspace/interactions" / session_id / turn_id / "authority_commit.json"
    artifact = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
    assert artifact["session_id"] == session_id and artifact["turn_id"] == turn_id and artifact["authoritative"]
    return events, artifact


def assert_result(case, result, state, expected, requests, alternate, headers, events, artifact, first):
    if case == "empty-target":
        assert type(result) is ValueError and "resolution_mode=unresolved" in str(result)
        assert len(requests) == 1 and requests[0][0].startswith("GET ") and not alternate
        assert "request" not in state and "constructor" not in state
        return {"empty_target_refused": True, "path": "primary", "result": "success"}
    assert result == {"post_finalize_wait_ms": 0}
    assert len(requests) == 2 and not alternate
    assert requests[0][0].startswith("GET /v1/models ") and requests[1][0].startswith("POST /v1/chat/completions ")
    assert requests[1][1]["messages"] == expected["input_config"]["messages"]
    assert requests[1][1]["model"] == "fixture" and requests[1][1]["stream"] is False
    assert state["request"] == expected and state["constructor"]["timeout_s"] == 8
    assert state["constructor"]["api_key_original"] and all(row["authorization"] == "Bearer fixture-original-key" for row in headers)
    assert state["post_finished"].is_set() and state["post_thread"] == threading.get_ident()
    assert state["native_clients"] and all(client.is_closed for client in state["native_clients"])
    assert all(thread != threading.get_ident() for thread in state["native_threads"])
    token_events = [event for event in events if event["event_type"] == "token_delta"]
    assert len(token_events) == 1 and token_events[0]["payload"]["delta"] == "original request"
    assert token_events[0]["payload"]["authoritative"] is False
    assert events[-1]["payload"]["commit_outcome"] == "ok"
    assert artifact["intents"] == [{"type": "turn_finalize", "ref": "model_stream_v1", "payload_digest": None}]
    if case == "resolver-context":
        assert state["target"]["gguf_model_root"] == str(first / "models") and state["target"]["status"] == "OK"
    return {"admitted_inputs_used": True, "real_catalog_and_completion": True, "durable_commit_verified": True,
            "path": "primary", "result": "success"}


async def observe(root, first, other, case, monkeypatch):
    state = {"arrived": asyncio.Event(), "release": asyncio.Event(), "post_finished": threading.Event()}
    install_observers(monkeypatch, state, case)
    input_config, turn_params = input_values(case)
    expected = snapshot_inputs(input_config, turn_params)
    manager = InteractionManager(stream_enabled=True, bus=StreamBus(), project_root=root,
                                 commit_orchestrator=CommitOrchestrator(project_root=root))
    headers = []
    async with observed_http_server(partial(response, state=state, case=case), allow_disconnect=True,
                                   request_headers=headers) as original, observed_http_server(
            partial(response, state=state, case=case, alternate=True)) as alternate:
        configure(monkeypatch, first, original[0], case)
        session_id = await manager.start({})
        queue = await manager.bus.subscribe(session_id)
        turn_id = await manager.begin_turn(session_id, input_config, turn_params)
        context = await manager.create_context(session_id, turn_id)
        active = asyncio.create_task(public_caller(run_builtin_workload(workload_id="model_stream_v1",
            input_config=input_config, turn_params=turn_params, interaction_context=context)))
        try:
            await asyncio.wait_for(state["arrived"].wait(), 5)
            mutate(monkeypatch, other, alternate[0], case, input_config, turn_params)
            state["release"].set()
            result = await asyncio.wait_for(active, 12)
            # Observe completion independently of workload result adoption.
            if "post_thread" in state:
                assert await asyncio.to_thread(state["post_finished"].wait, 5)
            events, artifact = await complete_interaction(manager, session_id, turn_id, queue, result, root)
            observed = {"case": case, "outcome_type": type(result).__name__, "requests": original[1],
                "alternate_requests": alternate[1], "request": state.get("request"), "constructor": state.get("constructor"),
                "events": events, "commit": artifact, "target": state.get("target"),
                "authorization_matches": [row.get("authorization") == "Bearer fixture-original-key" for row in headers]}
            await asyncio.to_thread(write_payload_with_diff_ledger, root / "stream-after-operation.json", observed)
            return assert_result(case, result, state, expected, original[1], alternate[1], headers, events, artifact, first)
        finally:
            state["release"].set()
            await asyncio.wait_for(asyncio.gather(active, return_exceptions=True), 12)
            if "post_thread" in state:
                assert await asyncio.to_thread(state["post_finished"].wait, 5)
            await manager.aclose()


async def exercise(root, case):
    first, other = await asyncio.to_thread(seed_roots, root)
    prepared = await prepare_logging(LoggingInputs(root, timezone_name="MST"))
    with pytest.MonkeyPatch.context() as monkeypatch, bind_logging(prepared):
        result = await observe(root, first, other, case, monkeypatch)
    return {**result, "case": case}


def main():
    root = Path(sys.argv[1]).resolve()
    result = asyncio.run(exercise(root, sys.argv[2]))
    process = psutil.Process()
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
        owner_origin=str(Path(owned_io.__file__).resolve()),
        owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        process_identity={"pid": process.pid, "create_time": process.create_time()},
        workload_source={"path": str(Path(workload.__file__).resolve()),
                         "sha256": hashlib.sha256(Path(workload.__file__).read_bytes()).hexdigest()})
    write_payload_with_diff_ledger(root / "result.json", result)


if __name__ == "__main__":
    main()
