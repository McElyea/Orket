"""Integration: quickstart native operations preserve chain state and truthful effects."""
import asyncio
import json
import threading
from pathlib import Path

import pytest

from orket.quickstart import governed_action_demo as demo
from orket.quickstart.ledger import QuickstartLedgerWriter, load_ledger_events, verify_ledger_events
from tests.helpers.application_root_controls import NativeHold
from tests.helpers.runtime_verification_hold import hold_stream, sqlite_response
from tests.integration.test_governed_demo_ownership import file_exists, observe_held
from tests.integration.test_marshaller_publication_ownership import assert_outcome, roots
from tests.quickstart.test_quickstart_ledger import _timestamp_factory

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def read_events(path):
    text = await asyncio.to_thread(path.read_text, encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@pytest.mark.parametrize("phase,operation", [
    ("create", "open"), ("create", "close"), ("emit", "open"),
    ("emit", "write"), ("emit", "close"), ("load", "readline"), ("load", "close"),
])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_quickstart_ledger_native_lifetime(tmp_path, monkeypatch, phase, operation, stop, failure, record_property):
    first, other = await roots(tmp_path)
    path = first / "ledger.jsonl"
    writer = None
    if phase != "create":
        writer = await QuickstartLedgerWriter.create(path=path, run_id="admitted", timestamp_factory=_timestamp_factory())
    if phase == "load":
        await writer.emit("first", {"value": 1})
    hold = hold_stream(monkeypatch, path, operation, failure=failure)
    payload = {"nested": ["admitted"]}
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            if phase == "create":
                return await QuickstartLedgerWriter.create(path=path, run_id="admitted", timestamp_factory=_timestamp_factory())
            if phase == "emit":
                return await writer.emit("first", payload)
            return await load_ledger_events(path)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        payload["nested"].append("late")
        if writer:
            writer.path = other / "redirected.jsonl"
            writer.run_id = "late-run"
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        assert all(stream.closed for stream in hold.streams)
        assert not await file_exists(other / "redirected.jsonl")
        if phase == "emit" and not (operation == "open" and failure):
            rows = await read_events(path)
            assert len(rows) == 1 and rows[0]["payload"] == {"nested": ["admitted"]}
            assert rows[0]["run_id"] == "admitted" and verify_ledger_events(rows).valid
            if not failure:
                writer.path, writer.run_id = path, "admitted"
                await writer.emit("second", {"value": 2})
                assert verify_ledger_events(await read_events(path)).valid
        if phase == "create":
            assert await asyncio.to_thread(path.read_bytes) == b""
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize("phase", ["input", "write", "verify"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_quickstart_demo_retains_native_effects(tmp_path, monkeypatch, phase, stop, failure, record_property):
    first, other = await roots(tmp_path)
    output = first / demo.OUTPUT_RELATIVE_PATH
    decision = first / "decision.txt"
    await asyncio.to_thread(decision.write_text, "approve", encoding="utf-8")
    hold = (NativeHold() if phase == "input" else
            hold_stream(monkeypatch, output, "write" if phase == "write" else "read", failure=failure))

    def read_input(_prompt):
        if phase != "input":
            return decision.read_text(encoding="utf-8")
        hold.wait()
        try:
            value = decision.read_text(encoding="utf-8")
            if failure:
                raise OSError("controlled native operator failure")
            return value
        finally:
            hold.finished.set()

    lines, deadline = [], asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await demo.run_governed_action_demo(workspace=first, input_func=read_input, output_func=lines.append,
                run_id_factory=lambda: "native-demo", timestamp_factory=_timestamp_factory())

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        events = await read_events(first / ".orket/quickstart/runs/native-demo/ledger.jsonl")
        assert verify_ledger_events(events).valid
        assert events[-1]["event_type"] == ("run_finished" if stop == "none" and not failure else
                                            "approval_requested" if phase == "input" else "operator_approved")
        assert await file_exists(output) == (phase != "input" or (stop == "none" and not failure))
        assert ("action: executed" in lines) == (stop == "none" and not failure)
        assert not await file_exists(other / ".orket")
        assert all(stream.closed for stream in getattr(hold, "streams", []))
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_quickstart_relative_root_survives_operator_wait(tmp_path, monkeypatch, record_property):
    first, other = await roots(tmp_path)
    monkeypatch.chdir(first)
    hold = NativeHold()

    def read_input(_prompt):
        hold.wait()
        hold.finished.set()
        return "approve"

    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await demo.run_governed_action_demo(workspace=Path(), input_func=read_input, output_func=lambda _: None,
                run_id_factory=lambda: "relative-demo", timestamp_factory=_timestamp_factory())

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, "none", other, monkeypatch, record_property)
        assert not isinstance(result, BaseException), repr(result)
        assert result.output_path == first / demo.OUTPUT_RELATIVE_PATH
        assert not await file_exists(other / "quickstart_out")
        assert verify_ledger_events(await read_events(result.ledger_path)).valid
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_quickstart_output_callback_uses_native_owner(tmp_path, record_property):
    hold = NativeHold()
    transcript = tmp_path / "console.txt"

    def output(text):
        if not hold.entered.is_set():
            hold.worker = threading.get_ident()
            hold.entered.set()
            assert hold.release.wait(1), "output callback blocked the event loop"
        with transcript.open("a", encoding="utf-8") as stream:
            stream.write(text + "\n")
        hold.finished.set()

    task = asyncio.create_task(demo.run_governed_action_demo(workspace=tmp_path, input_func=lambda _: "deny",
        output_func=output, run_id_factory=lambda: "output-demo", timestamp_factory=_timestamp_factory()))
    try:
        assert await asyncio.to_thread(hold.entered.wait, 2)
        assert hold.worker != threading.get_ident()
        assert await sqlite_response(tmp_path / "observer.sqlite", record_property) < 0.5
        hold.release.set()
        result = await asyncio.wait_for(task, 5)
        assert result.terminal_status == "denied_skipped"
        assert "action: skipped" in await asyncio.to_thread(transcript.read_text, encoding="utf-8")
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
