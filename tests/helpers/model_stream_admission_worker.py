"""Actual nonempty blocked resolver observations must not reach local inference requests."""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import psutil
import pytest

import orket
from orket.adapters.execution import owned_io
from orket.application.interactions.commit import CommitOrchestrator
from orket.application.interactions.manager import InteractionManager
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.exceptions import ModelConnectionError
from orket.logging import bind_logging, prepare_logging
from orket.streaming import StreamBus
from orket.streaming.model_provider import OpenAICompatModelStreamProvider
from orket.workloads import model_stream_v1 as workload
from orket.workloads import run_builtin_workload
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.model_stream_input_controls import configure, input_values
from tests.helpers.model_stream_input_worker import complete_interaction
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.sdk_observation_controls import public_caller


def prepare_root(root, case):
    models = root / "models"
    models.mkdir()
    if case != "empty-gguf":
        name = "other" if case == "missing-gguf" else "fixture"
        (models / (name + ".gguf")).write_bytes(b"admission inventory fixture; no model inference")


def install(monkeypatch, root, address, case, state):
    configure(monkeypatch, root, address, "control")
    provider = "openai_compat" if case in {"quarantined-openai", "admitted-openai", "empty-model"} else "llama_cpp"
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_PROVIDER", provider)
    if case.startswith("quarantined-"):
        # The canonical backend pair must also quarantine a requested llama_cpp alias.
        monkeypatch.setenv("ORKET_PROVIDER_MODEL_QUARANTINE", "openai_compat:fixture")
    resolve, construct = workload.resolve_provider_runtime_target, OpenAICompatModelStreamProvider.__init__

    async def observed(**options):
        target = await resolve(**options)
        state["target"] = target.to_payload()
        return target

    def constructed(owner, **options):
        state["construction_calls"] += 1
        return construct(owner, **options)

    monkeypatch.setattr(workload, "resolve_provider_runtime_target", observed)
    monkeypatch.setattr(OpenAICompatModelStreamProvider, "__init__", constructed)


async def respond(request):
    first, body = request
    if first.startswith("GET /v1/models "):
        return 200, {"data": [{"id": "fixture"}]}
    assert first.startswith("POST /v1/chat/completions ") and body["model"] == "fixture"
    return 200, {"choices": [{"message": {"content": "admitted completion"}}], "usage": {"completion_tokens": 1}}


def assert_admission(case, result, state, requests, events, artifact):
    target = state["target"]
    assert target["available_models"] == ("fixture",)
    if case.startswith("admitted-"):
        assert target["status"] == "OK" and target["model_id"] == "fixture"
        assert result == {"post_finalize_wait_ms": 0} and state["construction_calls"] == 1
        assert len(requests) == 2 and requests[-1][0].startswith("POST ")
        assert events[-1]["payload"]["commit_outcome"] == "ok"
        assert artifact["intents"][0]["ref"] == "model_stream_v1"
        return {"observed_path": "primary", "observed_result": "success", "admission": "allowed"}
    assert target["status"] == "BLOCKED"
    if case == "empty-model":
        assert not target["model_id"] and type(result) is ValueError
    else:
        assert target["model_id"] == "fixture", "control did not reproduce a nonempty blocked target"
        expected = "quarantined_model" if case.startswith("quarantined-") else (
            "gguf_model_missing" if case == "missing-gguf" else "gguf_inventory_empty")
        assert target["resolution_mode"] == expected
        assert type(result) is ModelConnectionError and f"resolution_mode={expected}" in str(result)
    assert state["construction_calls"] == 0 and len(requests) == 1
    assert requests[0][0].startswith("GET /v1/models ")
    assert not any(event["event_type"] in {"model_selected", "model_ready", "token_delta"} for event in events)
    assert not any(value["ref"] == "model_stream_v1" for value in artifact["intents"])
    return {"observed_path": "primary", "observed_result": "failure", "admission": "refused",
            "nonempty_blocked": case != "empty-model", "outcome_type": type(result).__name__}


async def observe(root, case, monkeypatch):
    state = {"construction_calls": 0}
    manager = InteractionManager(stream_enabled=True, bus=StreamBus(), project_root=root,
                                 commit_orchestrator=CommitOrchestrator(project_root=root))
    async with observed_http_server(respond) as server:
        install(monkeypatch, root, server[0], case, state)
        input_config, turn_params = input_values("empty-target" if case == "empty-model" else "control")
        session_id = await manager.start({})
        queue = await manager.bus.subscribe(session_id)
        turn_id = await manager.begin_turn(session_id, input_config, turn_params)
        context = await manager.create_context(session_id, turn_id)
        try:
            result = await public_caller(run_builtin_workload(workload_id="model_stream_v1",
                input_config=input_config, turn_params=turn_params, interaction_context=context))
            events, artifact = await complete_interaction(manager, session_id, turn_id, queue, result, root)
            await asyncio.to_thread(write_payload_with_diff_ledger, root / "admission-after-operation.json", {
                "case": case, "target": state["target"], "construction_calls": state["construction_calls"],
                "outcome_type": type(result).__name__, "requests": server[1], "events": events, "commit": artifact})
            return assert_admission(case, result, state, server[1], events, artifact)
        finally:
            await manager.aclose()


async def exercise(root, case):
    await asyncio.to_thread(prepare_root, root, case)
    prepared = await prepare_logging(LoggingInputs(root, timezone_name="MST"))
    with pytest.MonkeyPatch.context() as monkeypatch, bind_logging(prepared):
        proof = await observe(root, case, monkeypatch)
    return {**proof, "case": case, "refusal_policy_verified": True}


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
