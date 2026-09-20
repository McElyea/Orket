"""Integration: retained manager preflight captures inputs before any worker can await."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from orket.extensions import manager as manager_module
from tests.integration.test_sdk_process_control_plane import admitted_sdk as admitted_sdk
from tests.integration.test_workload_publication_inputs import admitted_legacy as admitted_legacy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _hold_preflight(monkeypatch):
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = manager_module.sha256_file

    def held(path):
        entered.set()
        try:
            assert release.wait(10)
            return original(path)
        finally:
            settled.set()

    monkeypatch.setattr(manager_module, "sha256_file", held)
    return entered, release, settled


@pytest.mark.parametrize("family", ["sdk", "legacy"])
async def test_preflight_keeps_original_policy_and_nested_inputs(tmp_path, admitted_sdk, admitted_legacy, monkeypatch, family):
    manager, payload = admitted_sdk if family == "sdk" else admitted_legacy
    payload["nested"] = {"value": "admitted"}
    monkeypatch.setenv("ORKET_EXT_PROVENANCE_VERBOSE", "true")
    monkeypatch.setenv("ORKET_RELIABLE_MODE", "false")
    entered, release, settled = _hold_preflight(monkeypatch)
    task = asyncio.create_task(manager.run_workload(
        workload_id="fixture" if family == "sdk" else "mystery_v1", input_config=payload,
        workspace=tmp_path, department="core"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        started = asyncio.get_running_loop().time()
        await asyncio.to_thread((tmp_path / "responsive").write_text, "ready", encoding="utf-8")
        assert asyncio.get_running_loop().time() - started < 0.5
        monkeypatch.setenv("ORKET_EXT_PROVENANCE_VERBOSE", "false")
        monkeypatch.setenv("ORKET_RELIABLE_MODE", "true")
        payload["nested"]["value"] = "rotated"
        release.set()
        result = await asyncio.wait_for(task, 10)
        provenance = json.loads(await asyncio.to_thread(Path(result.provenance_path).read_text, encoding="utf-8"))
        assert provenance["input_config"]["nested"] == {"value": "admitted"}
        assert provenance["reliable_mode"] is False and settled.is_set()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_preflight_interruption_drains_without_entering_workload(tmp_path, admitted_sdk, monkeypatch, stop):
    manager, payload = admitted_sdk
    entered, release, settled = _hold_preflight(monkeypatch)
    task = asyncio.create_task(manager.run_workload(workload_id="fixture", input_config=payload,
                                                   workspace=tmp_path, department="core"))
    request = task
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if stop == "timeout":
            request = asyncio.create_task(asyncio.wait_for(task, 0.05))
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.1)
        assert not request.done() and not settled.is_set()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert isinstance(result, TimeoutError if stop == "timeout" else asyncio.CancelledError)
        assert settled.is_set() and not (tmp_path / "sdk-effect").exists()
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, task, return_exceptions=True), 5)
