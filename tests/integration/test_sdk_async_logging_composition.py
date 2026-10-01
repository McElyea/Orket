"""Integration: actual SDK children preserve coroutine capability receipts and native outcomes."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import replace

import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.extensions.sdk_capability_authorization import HostCapabilityControls, build_host_authorization_envelope
from orket.extensions.sdk_workload_runner import SdkSubprocessRunError, run_sdk_workload_in_subprocess
from tests.helpers.log_process_receipts import process_readback
from tests.helpers.sdk_lifetime import sdk_request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
SOURCE = '''import asyncio
import os
from pathlib import Path
from orket_extension_sdk import WorkloadResult
from orket_extension_sdk.llm import GenerateRequest
from orket_extension_sdk.memory import MemoryWriteRequest

def mark(ctx):
    (Path(ctx.workspace_root) / "sdk-pid").write_text(str(os.getpid()))

def operation(ctx, payload):
    if payload["case"] == "denied":
        ctx.capabilities.memory_writer().write(MemoryWriteRequest(
            scope="profile_memory", key="companion_setting.role_id", value="unadmitted"))
        raise AssertionError("denied memory write reached its following statement")
    response = ctx.capabilities.llm().generate(GenerateRequest(system_prompt="system", user_message="hello"))
    if payload["case"] == "work_error":
        raise ValueError("controlled failure after admitted capability")
    return WorkloadResult(ok=True, output={"text": response.text, "model": response.model})

def sync_run(ctx, payload):
    mark(ctx)
    return operation(ctx, payload)

async def async_run(ctx, payload):
    await asyncio.sleep(0)
    await asyncio.to_thread(mark, ctx)
    return operation(ctx, payload)

def factory_run(ctx, payload):
    return async_run(ctx, payload)

class UnsupportedAwaitable:
    def __await__(self):
        yield
        return WorkloadResult(ok=True)

def unsupported_run(ctx, payload):
    mark(ctx)
    return UnsupportedAwaitable()
'''


STARTUP_SOURCE = """
import atexit
import inspect
import json
import threading

async def startup_body(ctx):
    await asyncio.to_thread((Path(ctx.workspace_root) / "startup-body-entered").write_text, "entered")
    return WorkloadResult(ok=True)

def startup_run(ctx, payload):
    mark(ctx)
    root = Path(ctx.workspace_root)
    workload = startup_body(ctx)
    original_start = threading.Thread.start
    attempts = []

    def start(thread):
        if thread.name != "orket-log-writer":
            return original_start(thread)
        attempts.append(thread)
        if payload["phase"] == "after":
            original_start(thread)
        raise OSError("controlled SDK writer start failure")

    def observe():
        threading.Thread.start = original_start
        writer = attempts[0] if attempts else None
        observation = {"coroutine_state": inspect.getcoroutinestate(workload),
            "start_attempts": len(attempts), "body_entered": (root / "startup-body-entered").exists(),
            "writer_started": writer is not None and writer.ident is not None,
            "writer_alive_at_exit": writer is not None and writer.is_alive()}
        (root / "startup-observation.json").write_text(json.dumps(observation), encoding="utf-8")

    atexit.register(observe)
    threading.Thread.start = start
    return workload
"""


@pytest.fixture
def observed_commands(monkeypatch):
    observations = []
    original = CommandProcessSupervisor.run

    async def observe(owner, *args, **kwargs):
        result = await original(owner, *args, **kwargs)
        observations.append(result)
        return result

    monkeypatch.setattr(CommandProcessSupervisor, "run", observe)
    return observations


def _request(root, style, case):
    options = sdk_request(root)
    original = options["workload"]
    name = original.entrypoint.split(":")[0]
    workload = replace(original, entrypoint=name + ":" + style + "_run",
                       required_capabilities=("model.generate", "memory.write"))
    extension = replace(options["extension"], manifest_entries=(workload,),
                        allowed_stdlib_modules=("asyncio", "os", "pathlib"))
    source = root / "extension" / (name + ".py")
    if style == "startup":
        extension = replace(extension, allowed_stdlib_modules=(*extension.allowed_stdlib_modules,
                            "atexit", "inspect", "json", "threading"))
    source.write_text(SOURCE + (STARTUP_SOURCE if style == "startup" else ""), encoding="utf-8")
    context = replace(options["sdk_ctx"], config={"capabilities": {
        "model.generate": {"provider": "static_llm", "text": "actual static result", "model": "static-fixture"}}})
    envelope = build_host_authorization_envelope(extension_id=extension.extension_id,
        workload_id=workload.workload_id, run_id=context.run_id,
        declared_capabilities=list(workload.required_capabilities), controls=HostCapabilityControls(admit_only=("model.generate",)))
    options.update(extension=extension, workload=workload, sdk_ctx=context, input_payload={"case": case},
                   authorization_envelope=envelope, timeout_seconds=15)
    return options


async def _prepare(tmp_path, monkeypatch, style, case):
    exchanges = tmp_path / "exchanges"
    await asyncio.to_thread(exchanges.mkdir)
    monkeypatch.setattr(tempfile, "tempdir", str(exchanges))
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_TIMEZONE", "MST")
    monkeypatch.setenv("ORKET_LOG_QUEUE_MAX", "10000")
    return exchanges, await asyncio.to_thread(_request, tmp_path, style, case)


async def _assert_lifetime(tmp_path, exchanges, caplog, expected_exit, record_property, observed_commands):
    events = [row.orket_record for row in caplog.records if row.message == "sdk_workload_process_observed"]
    assert len(events) == 1
    record = events[0]
    assert record["event"] == "sdk_workload_process_observed" and record["role"] == "system"
    runtime_event = record["data"]["runtime_event"]
    assert isinstance(runtime_event, dict)
    assert runtime_event["event"] == record["event"] and runtime_event["role"] == record["role"]
    lifetime = {key: value for key, value in record["data"].items() if key != "runtime_event"}
    command, = observed_commands
    assert command.returncode == expected_exit and lifetime == command.lifetime()
    assert lifetime["reason"] == "completed"
    assert lifetime["cleanup_confirmed"] and lifetime["capture_complete"]
    child_pid = int(await asyncio.to_thread((tmp_path / "sdk-pid").read_text))
    assert child_pid != os.getpid()
    identities = {pid: None for pid in (child_pid, lifetime["command_pid"], lifetime["supervisor_pid"], lifetime["transport_pid"])
                  if pid is not None}
    observed = await asyncio.to_thread(process_readback, identities)
    assert all(row["status"] in {"absent", "reused"} for row in observed.values())
    assert not await asyncio.to_thread(lambda: list(exchanges.iterdir()))
    record_property("sdk_child_lifetime", json.dumps({"lifetime": lifetime, "runtime_event": runtime_event, "returncode": command.returncode, "processes": observed}))


def _assert_report(report, envelope, case):
    assert report["authorization_digest"] == envelope.authorization_digest
    assert report["authorization_basis"] == envelope.authorization_basis and report["policy_version"] == envelope.policy_version
    assert report["declared_capabilities"] == ["memory.write", "model.generate"]
    assert report["admitted_capabilities"] == ["model.generate"]
    assert report["instantiated_capabilities"] == ["artifact.root", "model.generate", "workspace.root"]
    call, = report["call_records"]
    denied = case == "denied"
    assert report["used_capabilities"] == ["memory.write" if denied else "model.generate"]
    assert call["capability_id"] == report["used_capabilities"][0] and call["declared"] is True
    assert call["admitted"] is (not denied) and call["side_effect_observed"] is False
    assert call["observed_result"] == ("blocked" if denied else "success")
    assert call["denial_class"] == ("denied" if denied else "")
    assert call["error_code"] == ("E_SDK_CAPABILITY_DENIED" if denied else "")
    assert report["blocked_calls"] == ([call] if denied else [])


@pytest.mark.parametrize("style", ["sync", "async"])
@pytest.mark.parametrize("case", ["admitted", "denied", "work_error"])
async def test_actual_sdk_child_keeps_capability_and_workload_outcomes(tmp_path, monkeypatch, caplog, record_property, observed_commands, style, case):
    exchanges, options = await _prepare(tmp_path, monkeypatch, style, case)
    if case == "admitted":
        result = await run_sdk_workload_in_subprocess(**options)
        assert result.workload_result.ok is True
        assert result.workload_result.output == {"text": "actual static result", "model": "static-fixture"}
        report = result.capability_report
    else:
        expected = "E_SDK_CAPABILITY_DENIED: memory.write" if case == "denied" else "controlled failure after admitted capability"
        with pytest.raises(SdkSubprocessRunError, match=expected) as caught:
            await run_sdk_workload_in_subprocess(**options)
        assert caught.value.error_code == "ValueError"
        report = caught.value.capability_report
    _assert_report(report, options["authorization_envelope"], case)
    await _assert_lifetime(tmp_path, exchanges, caplog, int(case != "admitted"), record_property, observed_commands)
    assert not await asyncio.to_thread(lambda: list(tmp_path.rglob("*.sqlite3")))
    record_property("sdk_capability_report", json.dumps(report))


async def test_actual_sdk_child_admits_existing_coroutine_factory_shape(tmp_path, monkeypatch, caplog, record_property, observed_commands):
    exchanges, options = await _prepare(tmp_path, monkeypatch, "factory", "admitted")
    result = await run_sdk_workload_in_subprocess(**options)
    assert result.workload_result.output == {"text": "actual static result", "model": "static-fixture"}
    _assert_report(result.capability_report, options["authorization_envelope"], "admitted")
    await _assert_lifetime(tmp_path, exchanges, caplog, 0, record_property, observed_commands)


async def test_actual_sdk_child_retains_non_coroutine_awaitable_refusal(tmp_path, monkeypatch, caplog, record_property, observed_commands):
    exchanges, options = await _prepare(tmp_path, monkeypatch, "unsupported", "admitted")
    with pytest.raises(SdkSubprocessRunError, match="a coroutine was expected") as caught:
        await run_sdk_workload_in_subprocess(**options)
    assert caught.value.error_code == "ValueError"
    assert caught.value.capability_report["used_capabilities"] == []
    assert caught.value.capability_report["call_records"] == []
    assert caught.value.capability_report["authorization_digest"] == options["authorization_envelope"].authorization_digest
    await _assert_lifetime(tmp_path, exchanges, caplog, 1, record_property, observed_commands)


@pytest.mark.parametrize("phase", ["before", "after"])
async def test_actual_sdk_child_closes_coroutine_after_logging_preparation_failure(
        tmp_path, monkeypatch, caplog, record_property, observed_commands, phase):
    exchanges, options = await _prepare(tmp_path, monkeypatch, "startup", "admitted")
    options["input_payload"]["phase"] = phase
    with pytest.raises(SdkSubprocessRunError, match="controlled SDK writer start failure") as caught:
        await run_sdk_workload_in_subprocess(**options)
    assert caught.value.error_code == "OSError"
    report = caught.value.capability_report
    assert report["authorization_digest"] == options["authorization_envelope"].authorization_digest
    assert report["admitted_capabilities"] == ["model.generate"]
    assert report["instantiated_capabilities"] == ["artifact.root", "model.generate", "workspace.root"]
    assert report["used_capabilities"] == report["call_records"] == report["blocked_calls"] == []
    observation = json.loads(await asyncio.to_thread((tmp_path / "startup-observation.json").read_text, encoding="utf-8"))
    assert observation == {"coroutine_state": "CORO_CLOSED", "start_attempts": 1, "body_entered": False,
        "writer_started": phase == "after", "writer_alive_at_exit": phase == "after"}
    assert not await asyncio.to_thread((tmp_path / "startup-body-entered").exists)
    await _assert_lifetime(tmp_path, exchanges, caplog, 1, record_property, observed_commands)
    record_property("sdk_startup_failure_observation", json.dumps(observation))
