"""Layer: integration. Factory telemetry retains values, workspace and ledger authority."""
import asyncio
import logging
import threading
from types import SimpleNamespace

import pytest

from orket.application.services import dual_write_telemetry
from orket.core.contracts.log_event_inputs import LOG_EVENT_INPUT_ERROR
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging
from tests.helpers.dual_ledger import start_values
from tests.helpers.dual_telemetry_inputs import (
    DIAGNOSTIC,
    PARITY,
    HookedPayload,
    HookedValue,
    assert_durable_start,
    assert_workspace_record,
    factory,
    fail_custom_sink,
    hold_real_log,
    observe_public_start,
    read_records,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stage", ["default", "custom_failure"])
@pytest.mark.parametrize("policy", ["legacy_default", "fail_fast"])
@pytest.mark.parametrize("stop", ["none", "cancel"])
async def test_factory_telemetry_captures_root_values_and_settles_real_effects(tmp_path, monkeypatch, stage, policy, stop):
    prepared = await prepare_logging(LoggingInputs(tmp_path, timezone_name="MST", missing_workspace_mode=policy))
    with bind_logging(prepared):
        repo = factory(tmp_path, sink=fail_custom_sink if stage == "custom_failure" else None)
        event = PARITY if stage == "default" else DIAGNOSTIC
        state = hold_real_log(monkeypatch, repo, event)
        await observe_public_start(repo, state, tmp_path, stop)
        await assert_durable_start(repo)
    assert repo.sink_failure_count == (0 if stage == "default" else 1)
    await assert_workspace_record(tmp_path, event, state.expected)
    if stage == "default":
        assert state.expected["phase"] == "start_run" and state.expected["session_id"] == "run"
        assert state.borrowed != state.expected
    else:
        assert state.expected == {"component": "run_ledger_dual_write", "error_type": "RuntimeError",
                                  "error": "supplied telemetry sink refused"}


@pytest.mark.parametrize("kind", ["container_subclass", "native_conversion"])
async def test_default_telemetry_refuses_hooks_before_native_publication(tmp_path, kind):
    """Direct telemetry-owner guard; the public factory supplies its real binding."""
    prepared = await prepare_logging(LoggingInputs(tmp_path, missing_workspace_mode="fail_fast"))
    with bind_logging(prepared):
        repo = factory(tmp_path)
        hook = HookedPayload(kind="unsupported") if kind == "container_subclass" else HookedValue()
        payload = hook if kind == "container_subclass" else {"kind": "unsupported", "value": hook}
        await repo._telemetry.emit(payload)
    assert hook.calls == 0 and repo.sink_failure_count == 1
    row, = await read_records(tmp_path / "runtime-workspace/orket.log")
    assert row["event"] == DIAGNOSTIC
    assert row["data"]["error_type"] == "TypeError" and row["data"]["error"] == LOG_EVENT_INPUT_ERROR
    assert not await asyncio.to_thread((tmp_path / "workspace/default/orket.log").exists)


async def test_custom_sink_keeps_borrowed_identity_native_call_and_returned_awaitable(tmp_path, monkeypatch):
    prepared = await prepare_logging(LoggingInputs(tmp_path, missing_workspace_mode="fail_fast"))
    state = SimpleNamespace(borrowed=None, sink_payload=None, native_thread=None, async_thread=None, completed=False)
    marker = object()
    loop_thread = threading.get_ident()
    path = tmp_path / "custom-sink.txt"

    def sink(payload):
        state.sink_payload, state.native_thread = payload, threading.get_ident()
        payload["borrowed_custom_value"] = marker

        async def finish():
            state.async_thread = threading.get_ident()
            await asyncio.to_thread(path.write_text, "custom sink effect", encoding="utf-8")
            state.completed = True
        return finish()

    with bind_logging(prepared):
        repo = factory(tmp_path, sink=sink)
        actual_emit = repo._telemetry.emit

        async def observe(payload):
            state.borrowed = payload
            return await actual_emit(payload)

        monkeypatch.setattr(repo._telemetry, "emit", observe)
        await repo.start_run(**start_values())
        await assert_durable_start(repo)
    assert state.sink_payload is state.borrowed and state.borrowed["borrowed_custom_value"] is marker
    assert state.native_thread != loop_thread and state.async_thread == loop_thread and state.completed
    assert await asyncio.to_thread(path.read_text, encoding="utf-8") == "custom sink effect"
    assert repo.sink_failure_count == 0
    assert not await asyncio.to_thread((tmp_path / "runtime-workspace/orket.log").exists)


async def test_real_log_path_refusal_is_counted_once_without_lifecycle_authority(tmp_path, monkeypatch, caplog):
    prepared = await prepare_logging(LoggingInputs(tmp_path))
    workspace = tmp_path / "runtime-workspace"
    await asyncio.to_thread((workspace / "orket.log").mkdir, parents=True)
    errors, calls = [], []
    actual_log = dual_write_telemetry.log_event

    def observe(event, data=None, **options):
        calls.append(event)
        try:
            return actual_log(event, data, **options)
        except OSError as error:
            errors.append(error)
            raise

    monkeypatch.setattr(dual_write_telemetry, "log_event", observe)
    with bind_logging(prepared), caplog.at_level(logging.ERROR, logger=dual_write_telemetry.__name__):
        repo = factory(tmp_path)
        await repo.start_run(**start_values())
        await assert_durable_start(repo)
    assert repo.sink_failure_count == 1 and calls == [PARITY, DIAGNOSTIC]
    assert len(errors) == 2 and all(isinstance(error, OSError) for error in errors)
    record, = [row for row in caplog.records if row.name == dual_write_telemetry.__name__]
    assert record.getMessage() == "Dual ledger telemetry error could not be retained"
    assert record.exc_info[1] is errors[1]
    assert await asyncio.to_thread((workspace / "orket.log").is_dir)
    assert not await asyncio.to_thread((tmp_path / "workspace/default/orket.log").exists)
