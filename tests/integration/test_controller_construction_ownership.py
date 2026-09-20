"""Integration: real manager preparation and SDK dispatch retain native ownership."""
from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services import extension_catalog_commands as owner
from orket.extensions.controller_workload_runtime import build_controller_workload_runtime
from orket_extension_sdk.workloads.controller import ControllerWorkloadRunner
from tests.integration import test_sdk_process_control_plane as sdk_fixtures

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
admitted_sdk = sdk_fixtures.admitted_sdk


def context_and_envelope(tmp_path, manager, child_payload):
    ctx = SimpleNamespace(workspace_root=tmp_path / "project", workload_id="controller", run_id="construction",
                          config={"extensions_catalog_path": str(manager.catalog_path), "department": "core"})
    envelope = {"controller_contract_version": "controller.workload.v1", "controller_workload_id": "controller",
                "parent_depth": 0, "ancestry": [], "children": [{"target_workload": "fixture",
                "contract_style": "sdk_v0", "payload": child_payload}]}
    return ctx, envelope


async def test_disabled_builder_and_runner_do_not_construct_manager(tmp_path, monkeypatch):
    ctx = SimpleNamespace(workspace_root=tmp_path / "absent", workload_id="controller", run_id="disabled", config={})
    monkeypatch.setenv("ORKET_CONTROLLER_ENABLED", "0")
    original = Path.mkdir
    attempts = []

    def observed(path, *args, **kwargs):
        attempts.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", observed)
    runtime = build_controller_workload_runtime(ctx=ctx, payload={})
    monkeypatch.setenv("ORKET_CONTROLLER_ENABLED", "1")
    result = await ControllerWorkloadRunner(runtime=runtime).run(ctx=ctx, payload={})
    assert not result.ok
    assert result.output["controller_summary"]["error_code"] == "controller.disabled_by_policy"
    assert attempts == []
    assert not ctx.workspace_root.exists()


@pytest.mark.parametrize("stop", ["complete", "cancel", "caller-timeout"])
@pytest.mark.parametrize("refuse", [False, True])
async def test_preparation_retains_native_directory_worker(tmp_path, admitted_sdk, monkeypatch, stop, refuse):
    manager, child_payload = admitted_sdk
    ctx, envelope = context_and_envelope(tmp_path, manager, child_payload)
    ctx.workspace_root.mkdir()
    if refuse:
        (ctx.workspace_root / ".orket").write_text("native directory obstruction", encoding="utf-8")
    target = ctx.workspace_root / ".orket/durable/db"
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = Path.mkdir

    def held(path, *args, **kwargs):
        if path != target:
            return original(path, *args, **kwargs)
        entered.set()
        try:
            if not release.wait(10):
                raise RuntimeError("construction worker was not released")
            return original(path, *args, **kwargs)
        finally:
            settled.set()

    monkeypatch.setattr(Path, "mkdir", held)
    runtime = build_controller_workload_runtime(ctx=ctx, payload={})
    assert not entered.is_set()
    task = asyncio.create_task(runtime.dispatch(envelope_payload=envelope, workspace=ctx.workspace_root, department="core"))
    timeout_owner = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if stop == "cancel":
            task.cancel()
        elif stop == "caller-timeout":
            timeout_owner = asyncio.create_task(asyncio.wait_for(task, .01))
        started = time.monotonic()
        await asyncio.sleep(.03)
        assert time.monotonic() - started < .5
        assert not task.done() and not settled.is_set()
        if stop != "complete":
            assert task.cancelling() == 1
        if stop == "cancel":
            task.cancel()
        release.set()
        result_owner = timeout_owner or task
        if refuse:
            with pytest.raises(OSError):
                await asyncio.wait_for(result_owner, 10)
        elif stop != "complete":
            with pytest.raises(TimeoutError if timeout_owner else asyncio.CancelledError):
                await asyncio.wait_for(result_owner, 10)
        else:
            assert (await asyncio.wait_for(task, 15)).status == "success"
        assert settled.is_set()
        assert (ctx.workspace_root / "sdk-effect").exists() is (not refuse and stop == "complete")
        assert target.is_dir() is (not refuse)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, *([timeout_owner] if timeout_owner else []), return_exceptions=True)


async def test_queued_controller_retains_policy_catalog_workspace_and_child_input(tmp_path, admitted_sdk, monkeypatch):
    manager, child_payload = admitted_sdk
    ctx, envelope = context_and_envelope(tmp_path, manager, child_payload)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_CONTROLLER_ENABLED", "1")
    monkeypatch.setenv("ORKET_CONTROLLER_ALLOWED_DEPARTMENTS", "core")
    monkeypatch.setenv("ORKET_CONTROLLER_MAX_FANOUT", "5")
    payload = {"extensions_catalog_path": str(manager.catalog_path)}
    runtime = build_controller_workload_runtime(ctx=ctx, payload=payload)
    entered, release = asyncio.Event(), asyncio.Event()
    original = owner.run_owned_thread

    async def held(operation, **kwargs):
        entered.set()
        await release.wait()
        return await original(operation, **kwargs)

    monkeypatch.setattr(owner, "run_owned_thread", held)
    task = asyncio.create_task(runtime.dispatch(envelope_payload=envelope, workspace=Path("project"), department="core"))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        rotated = tmp_path / "rotated"
        rotated.mkdir()
        monkeypatch.chdir(rotated)
        monkeypatch.setenv("ORKET_CONTROLLER_ENABLED", "0")
        monkeypatch.setenv("ORKET_CONTROLLER_ALLOWED_DEPARTMENTS", "elsewhere")
        monkeypatch.setenv("ORKET_CONTROLLER_MAX_FANOUT", "1")
        monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", "missing.json")
        ctx.config["extensions_catalog_path"] = str(rotated / "missing.json")
        payload["extensions_catalog_path"] = str(rotated / "missing.json")
        child_payload["mode"] = "error"
        ctx.workspace_root = rotated
        assert runtime.is_enabled(payload={}, department="core")
        assert not runtime.is_enabled(payload={}, department="elsewhere")
        release.set()
        summary = await asyncio.wait_for(task, 15)
        assert summary.status == "success"
        assert summary.enforced_caps.max_fanout == 5
        assert (tmp_path / "project/sdk-effect").read_text() == "executed"
        assert (tmp_path / "project/.orket/durable/db/control_plane_records.sqlite3").is_file()
        assert not (rotated / "sdk-effect").exists()
        later = build_controller_workload_runtime(ctx=ctx, payload={})
        assert not later.is_enabled(payload={}, department="core")
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
