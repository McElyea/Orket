"""Layer: integration. native fixture capture and interruption."""
from __future__ import annotations

import asyncio
import contextlib
import json
import threading
import time
from pathlib import Path

import pytest

from orket.application.services.fixture_verification_service import FixtureVerificationService
from orket.logging import settle_log_write_frontier
from orket.schema import IssueVerification, VerificationScenario
from tests.helpers.fixture_input_controls import (
    HookedDict,
    fail_metadata,
    observation,
    prepare_native,
    selected_time,
)
from tests.helpers.runtime_verification_hold import hold_path, settle, sqlite_response, wait_entered
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ERROR = "E_FIXTURE_VERIFICATION_INPUT_UNSUPPORTED"


@pytest.mark.parametrize("boundary", ["verification", "scenario"])
async def test_fixture_refuses_custom_schema_models_before_native_effects(tmp_path, boundary):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    if boundary == "verification":
        custom = type("CustomVerification", (IssueVerification,), {})
        verification = custom.model_construct(fixture_path=verification.fixture_path, scenarios=verification.scenarios)
    else:
        custom = type("CustomScenario", (VerificationScenario,), {})
        original = verification.scenarios[0]
        verification.scenarios = [custom.model_construct(**dict(original))]
    with pytest.raises(TypeError, match=f"^{ERROR}$"):
        await FixtureVerificationService(tmp_path, utc_now=selected_time, environment={}).verify(verification)
    assert verification.scenarios[0].status == "pending"
    assert not await asyncio.to_thread((tmp_path / "verification/observed.json").exists)


@pytest.mark.parametrize("kind", ["hook", "cycle", "nan", "nonstring-key"])
async def test_fixture_unsupported_graph_refuses_without_hooks_or_child(tmp_path, record_property, kind):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    hook = HookedDict()
    cyclic = []
    cyclic.append(cyclic)
    value = {"hook": hook, "cycle": cyclic, "nan": float("nan"), "nonstring-key": {1: "bad"}}[kind]
    verification.scenarios[0].input_data["unsupported"] = value
    service = FixtureVerificationService(tmp_path, utc_now=selected_time, environment={})
    started = time.perf_counter()
    task = asyncio.create_task(service.verify(verification))
    try:
        assert await sqlite_response(tmp_path / "response.sqlite3", record_property, started) < 0.5
        with pytest.raises(TypeError, match=f"^{ERROR}$"):
            await task
        assert hook.calls == []
        assert verification.scenarios[0].status == "pending"
        assert not await asyncio.to_thread((tmp_path / "verification/observed.json").exists)
        assert not await asyncio.to_thread((tmp_path / "orket.log").exists)
    finally:
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout", "previous-handled"])
async def test_fixture_native_failure_precedence(tmp_path, monkeypatch, record_property, stop):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    failure = OSError("controlled fixture metadata failure")
    hold = fail_metadata(monkeypatch, tmp_path / "verification/fixture.py", failure)
    service = FixtureVerificationService(tmp_path, utc_now=selected_time, environment={})

    async def invoke():
        if stop == "previous-handled":
            asyncio.current_task().cancel("earlier handled interruption")
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.sleep(0)
        return await service.verify(verification)

    task = asyncio.create_task(invoke())
    waiter = None
    try:
        await wait_entered(hold)
        if stop == "cancel":
            task.cancel("first interruption")
            await asyncio.sleep(0)
            task.cancel("repeated interruption")
        elif stop == "timeout":
            waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
            await asyncio.sleep(0.04)
        assert await sqlite_response(tmp_path / "response.sqlite3", record_property) < 0.5
        assert not task.done() and (waiter is None or not waiter.done())
        hold.release.set()
        if stop in {"cancel", "timeout"}:
            with pytest.raises(OSError) as caught:
                await (waiter if waiter is not None else task)
            assert caught.value is failure
            assert verification.scenarios[0].status == "pending"
        else:
            result = await task
            assert result.failed == 1 and result.process_lifetime is None
            assert any("controlled fixture metadata failure" in line for line in result.logs)
        assert hold.finished.is_set() and not hold.expired
        assert hold.thread != threading.get_ident()
        assert not await asyncio.to_thread((tmp_path / "verification/observed.json").exists)
    finally:
        await settle(task, hold)
        if waiter is not None:
            await asyncio.gather(waiter, return_exceptions=True)


async def test_fixture_captures_root_path_and_provider_slots(tmp_path, monkeypatch):
    selected, later = tmp_path / "selected", tmp_path / "later"
    verification = await asyncio.to_thread(prepare_native, selected)
    await asyncio.to_thread(prepare_native, later)
    service = FixtureVerificationService(selected, utc_now=selected_time,
                                         environment={"FIXTURE_CAPTURE_VALUE": "original"})
    hold = hold_path(monkeypatch, "is_file", selected / "verification/fixture.py")
    task = asyncio.create_task(service.verify(verification))
    try:
        await wait_entered(hold)
        service.workspace, service.environment = later, {"FIXTURE_CAPTURE_VALUE": "later"}
        service.utc_now = lambda: pytest.fail("replacement clock selected")
        verification.fixture_path = "verification/later.py"
        hold.release.set()
        result = await task
        assert result.passed == 1 and result.timestamp == selected_time().isoformat()
        assert (await asyncio.to_thread(observation, selected))["policy"] == "original"
        assert not await asyncio.to_thread((later / "verification/observed.json").exists)
    finally:
        await settle(task, hold)


async def test_fixture_relative_root_remains_bound_after_cwd_rotation(tmp_path, monkeypatch):
    selected, later = tmp_path / "selected", tmp_path / "later"
    verification = await asyncio.to_thread(prepare_native, selected)
    await asyncio.to_thread(later.mkdir)
    monkeypatch.chdir(selected)
    service = FixtureVerificationService(Path(), utc_now=selected_time, environment={})
    hold = hold_path(monkeypatch, "is_file", selected / "verification/fixture.py")
    task = asyncio.create_task(service.verify(verification))
    try:
        await wait_entered(hold)
        monkeypatch.chdir(later)
        hold.release.set()
        result = await task
        assert result.passed == 1 and result.process_lifetime["cleanup_confirmed"]
        assert (await asyncio.to_thread(observation, selected))["cwd"] == str(selected / "verification")
    finally:
        await settle(task, hold)


async def test_fixture_cancelled_native_tree_logs_only_to_captured_root(tmp_path, monkeypatch, record_property):
    selected, later = tmp_path / "selected", tmp_path / "later"
    source = "import subprocess,sys,time\ndef verify(data):\n    subprocess.Popen([sys.executable,data['worker'],data['root'],'2'])\n    time.sleep(30)\n"
    verification = await asyncio.to_thread(prepare_native, selected, source)
    verification.scenarios[0].input_data = {"worker": str(WORKER), "root": str(selected)}
    await asyncio.to_thread(later.mkdir)
    monkeypatch.chdir(selected)
    service = FixtureVerificationService(Path(), utc_now=selected_time,
                                         environment={"ORKET_VERIFY_TIMEOUT_SEC": "15"})
    task = asyncio.create_task(service.verify(verification))
    processes = []
    try:
        processes = await await_tree(selected)
        identities = await asyncio.to_thread(lambda: [{"pid": process.pid, "created": process.create_time()}
                                                      for process in processes])
        monkeypatch.chdir(later)
        service.workspace = later
        task.cancel("stop selected fixture")
        await asyncio.sleep(0)
        task.cancel("repeat selected fixture")
        with pytest.raises(asyncio.CancelledError) as stopped:
            await asyncio.wait_for(task, 5)
        assert stopped.value.lifetime.cleanup_confirmed
        await assert_stopped(processes, selected)
        await asyncio.to_thread(settle_log_write_frontier)
        lines = await asyncio.to_thread((selected / "orket.log").read_text, encoding="utf-8")
        events = [json.loads(line) for line in lines.splitlines()]
        assert {row["event"] for row in events} == {"verification_process_cancelled", "fixture_verification_cancelled"}
        assert all(row["data"]["cleanup_confirmed"] for row in events)
        assert verification.scenarios[0].status == "pending"
        assert not await asyncio.to_thread((later / "orket.log").exists)
        record_property("fixture_native_cleanup", json.dumps({"processes": identities,
            "lifetime": stopped.value.lifetime.lifetime(), "stopped_before_emergency": True,
            "selected": str(selected), "later": str(later)}))
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, selected)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
