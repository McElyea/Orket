"""Integration: real API construction and native reads retain ownership through interruption."""
from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import httpx
import pytest

from orket.application.services import api_runtime_preparation as preparation
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class NativeReadHold:
    def __init__(self, target, monkeypatch):
        self.entered, self.release, self.settled = (threading.Event() for _ in range(3))
        self.threads = []
        original = Path.read_bytes

        def held(path):
            if path != target:
                return original(path)
            self.threads.append(threading.get_ident())
            self.entered.set()
            try:
                if not self.release.wait(10):
                    raise RuntimeError("API preparation worker was not released")
                return original(path)
            finally:
                self.settled.set()

        monkeypatch.setattr(Path, "read_bytes", held)


def observe_containers(monkeypatch):
    owners = []
    original = preparation.build_api_runtime_container

    def observed(*args, **kwargs):
        owner = original(*args, **kwargs)
        owners.append(owner)
        return owner

    monkeypatch.setattr(preparation, "build_api_runtime_container", observed)
    return owners


async def enter_and_close(app):
    async with app.router.lifespan_context(app):
        assert app.state.api_ready


@pytest.mark.parametrize("stop", ["complete", "cancel", "caller-timeout"])
@pytest.mark.parametrize("refuse", [False, True])
async def test_outbound_read_retains_constructed_owner(tmp_path, monkeypatch, stop, refuse):
    target = tmp_path / "outbound.json"
    if refuse:
        target.mkdir()  # The real native file read must fail after resources were constructed.
    else:
        await asyncio.to_thread(target.write_text, '{"policy_version":"captured"}', encoding="utf-8")
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_OUTBOUND_POLICY_CONFIG_PATH", "outbound.json")
    hold, owners = NativeReadHold(target, monkeypatch), observe_containers(monkeypatch)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    task = asyncio.create_task(enter_and_close(app))
    timeout_owner = None
    try:
        assert await asyncio.to_thread(hold.entered.wait, 5)
        assert len(owners) == 1 and not owners[0].closed and not app.state.api_ready
        assert hold.threads == [hold.threads[0]] and threading.get_ident() not in hold.threads
        if stop == "cancel":
            task.cancel()
        elif stop == "caller-timeout":
            timeout_owner = asyncio.create_task(asyncio.wait_for(task, .01))
        started = time.monotonic()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test") as client:
            assert (await client.get("/health")).status_code == 503
        await asyncio.sleep(.03)
        assert time.monotonic() - started < .5
        assert not task.done() and not hold.settled.is_set()
        if stop != "complete":
            assert task.cancelling() == 1
        if stop == "cancel":
            task.cancel()
        hold.release.set()
        result_owner = timeout_owner or task
        if refuse:
            with pytest.raises(OSError):
                await asyncio.wait_for(result_owner, 10)
        elif stop != "complete":
            with pytest.raises(TimeoutError if timeout_owner else asyncio.CancelledError):
                await asyncio.wait_for(result_owner, 10)
        else:
            await asyncio.wait_for(task, 10)
            assert app.state.outbound_policy_config == {"policy_version": "captured"}
        assert hold.settled.is_set() and owners[0].closed and owners[0].engine._closed
        assert owners[0].extension_runtime_service._model_provider._closed
        assert not app.state.api_ready and owners[0].active_background_task_count == 0
    finally:
        hold.release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, *([timeout_owner] if timeout_owner else []), return_exceptions=True)


async def test_native_failure_survives_repeated_cancellation_during_cleanup(tmp_path, monkeypatch):
    target = tmp_path / "missing-policy.json"
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_OUTBOUND_POLICY_CONFIG_PATH", str(target))
    owners = observe_containers(monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()
    original = preparation.close_owned_resource

    async def held(resource):
        entered.set()
        await release.wait()
        await original(resource)

    monkeypatch.setattr(preparation, "close_owned_resource", held)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    task = asyncio.create_task(enter_and_close(app))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        await asyncio.sleep(.01)
        task.cancel()
        await asyncio.sleep(.01)
        assert not task.done() and len(owners) == 1 and not owners[0].closed
        release.set()
        with pytest.raises(FileNotFoundError):
            await asyncio.wait_for(task, 10)
        assert owners[0].closed and not app.state.api_ready
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_later_composition_failure_closes_acquired_resources(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    # Conversion occurs in the real final governed-agent constructor, after engine,
    # interaction and model clients were acquired but before the container returns.
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_CAPACITY_LIMIT", "not-an-integer")
    acquired = []
    original = preparation.close_owned_resource

    async def observed(resource):
        await original(resource)
        acquired.append(resource)

    monkeypatch.setattr(preparation, "close_owned_resource", observed)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    with pytest.raises(ValueError):
        await enter_and_close(app)
    assert [type(resource).__name__ for resource in acquired] == [
        "ExtensionRuntimeService", "InteractionManager", "OrchestrationEngine"]
    assert acquired[0]._model_provider._closed and acquired[-1]._closed
    assert not app.state.api_ready
