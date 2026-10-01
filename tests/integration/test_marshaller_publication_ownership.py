"""Integration: artifact and ledger owners retain native publication and captured inputs."""
import asyncio
import json
from pathlib import Path

import pytest

from orket.marshaller.artifacts import MarshallerArtifacts
from orket.marshaller.ledger import LedgerWriter
from tests.helpers.application_root_controls import NativeHold
from tests.helpers.runtime_verification_hold import hold_stream
from tests.integration.test_governed_demo_ownership import file_exists, observe_held
from tests.marshaller.test_runner import _assert_ledger_chain, _read_ledger

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def roots(tmp_path):
    first, other = tmp_path / "first", tmp_path / "other"
    await asyncio.to_thread(first.mkdir)
    await asyncio.to_thread(other.mkdir)
    return first, other


def held_mkdir(monkeypatch, selected, failure):
    hold, native = NativeHold(), Path.mkdir

    def held(path, *args, **kwargs):
        if path != selected or hold.entered.is_set():
            return native(path, *args, **kwargs)
        hold.wait()
        try:
            value = native(path, *args, **kwargs)
            if failure:
                raise OSError("controlled native directory failure")
            return value
        finally:
            hold.finished.set()

    monkeypatch.setattr(Path, "mkdir", held)
    return hold


def assert_outcome(outcome, stop, failure):
    if failure:
        assert isinstance(outcome, OSError) and "controlled native" in str(outcome)
    elif stop != "none":
        assert isinstance(outcome, asyncio.CancelledError if stop == "cancel" else TimeoutError)
    else:
        assert not isinstance(outcome, BaseException)


@pytest.mark.parametrize("operation", ["directory", "write", "close"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_check_artifacts_retain_captured_values(tmp_path, monkeypatch, operation, stop, failure, record_property):
    first, other = await roots(tmp_path)
    artifacts = MarshallerArtifacts(first, "run")
    checks = artifacts.attempt_dir(1) / "checks"
    payload = {"status": "success", "nested": ["admitted"]}
    hold = (held_mkdir(monkeypatch, checks, failure) if operation == "directory" else
            hold_stream(monkeypatch, checks / "lint.json", operation, failure=failure))
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await artifacts.write_check(1, "lint", payload, "native check output\n")

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        payload["nested"].append("mutated")
        artifacts.run_root = other / "redirected"
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        if operation != "directory" or (stop == "none" and not failure):
            observed = json.loads(await asyncio.to_thread((checks / "lint.json").read_text, encoding="utf-8"))
            assert observed == {"status": "success", "nested": ["admitted"]}
        assert await file_exists(checks / "lint.log") == (stop == "none" and not failure)
        assert not await file_exists(other / "redirected")
        assert all(stream.closed for stream in getattr(hold, "streams", []))
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize("operation", ["directory", "write", "close"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_ledger_append_retains_digest_adoption(tmp_path, monkeypatch, operation, stop, failure, record_property):
    first, other = await roots(tmp_path)
    path = first / "run/ledger.jsonl"
    writer = LedgerWriter(path)
    payload = {"nested": ["admitted"]}
    hold = (held_mkdir(monkeypatch, path.parent, failure) if operation == "directory" else
            hold_stream(monkeypatch, path, operation, failure=failure))
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await writer.append("first", payload)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        payload["nested"].append("mutated")
        writer.ledger_path = other / "redirected.jsonl"
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        assert not await file_exists(other / "redirected.jsonl")
        rows = await asyncio.to_thread(_read_ledger, path) if await file_exists(path) else []
        assert len(rows) == int(operation != "directory" or not failure)
        if rows:
            _assert_ledger_chain(rows)
            assert rows[0]["payload"] == {"nested": ["admitted"]}
        assert writer.current_digest == (rows[0]["entry_digest"] if not failure else "")
        assert all(stream.closed for stream in getattr(hold, "streams", []))
        if not failure:
            writer.ledger_path = path
            await writer.append("second", {"value": 2})
            continued = await asyncio.to_thread(_read_ledger, path)
            assert [row["event_seq"] for row in continued] == [1, 2]
            _assert_ledger_chain(continued)
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize("operation", ["read", "close"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_ledger_resume_owns_native_read(tmp_path, monkeypatch, operation, stop, failure, record_property):
    first, other = await roots(tmp_path)
    path = first / "ledger.jsonl"
    original = LedgerWriter(path)
    await original.append("first", {"value": 1})
    before = await asyncio.to_thread(path.read_bytes)
    hold = hold_stream(monkeypatch, path, operation, failure=failure)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await LedgerWriter.resume(path)

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        assert all(stream.closed for stream in hold.streams)
        assert await asyncio.to_thread(path.read_bytes) == before
        if stop == "none" and not failure:
            assert result.current_digest == original.current_digest
            await result.append("second", {"value": 2})
            _assert_ledger_chain(await asyncio.to_thread(_read_ledger, path))
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_writers_bind_relative_construction_roots(tmp_path, monkeypatch):
    first, other = await roots(tmp_path)
    monkeypatch.chdir(first)
    artifacts, ledger = MarshallerArtifacts(Path(), "run"), LedgerWriter(Path("ledger.jsonl"))
    monkeypatch.chdir(other)
    await artifacts.write_patch(1, "actual patch")
    await ledger.append("event", {"value": 1})
    assert await file_exists(first / "workspace/default/stabilizer/run/run/attempts/1/patch.diff")
    assert await file_exists(first / "ledger.jsonl")
    assert not await file_exists(other / "workspace")
    assert not await file_exists(other / "ledger.jsonl")
