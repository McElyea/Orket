"""Integration: SDK publication retains actual file workers through interruption."""
from __future__ import annotations

import asyncio
import threading

import pytest

from orket.extensions import workload_executor as executor_module
from orket.extensions import workload_publication as publication_module
from tests.integration.test_sdk_process_control_plane import admitted_sdk as admitted_sdk
from tests.integration.test_sdk_process_control_plane import retained_records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _hold_worker(monkeypatch, manager, phase, *, legacy=False, failure=False):
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    artifact_methods = {"validate": "run_validators" if legacy else "validate_sdk_artifacts",
                        "manifest-build": "build_artifact_manifest",
                        "provenance-build": "build_provenance" if legacy else "build_sdk_provenance"}
    target = manager.workload_executor.artifacts if phase in artifact_methods else publication_module
    method = artifact_methods.get(phase, "digest_file" if phase == "digest" else "write_json_file")
    if phase == "root":
        target, method = executor_module, "prepare_artifact_root"
    elif phase == "compile":
        target, method = publication_module, "compile_workload"
    original = getattr(target, method)

    def held(*args, **kwargs):
        if phase.endswith("-write") and args[0].name != (
                "artifact_manifest.json" if phase == "manifest-write" else "provenance.json"):
            return original(*args, **kwargs)
        entered.set()
        try:
            if not release.wait(10):
                raise RuntimeError("publication worker was not released")
            if failure:
                raise PermissionError("controlled held worker refusal")
            return original(*args, **kwargs)
        finally:
            settled.set()

    monkeypatch.setattr(target, method, held)
    return entered, release, settled


@pytest.mark.parametrize("phase", ["validate", "manifest-build", "manifest-write", "provenance-build", "provenance-write", "digest"])
@pytest.mark.parametrize("stop", ["cancel", "caller-timeout"])
async def test_sdk_publication_retains_admitted_worker(tmp_path, admitted_sdk, monkeypatch, phase, stop):
    manager, payload = admitted_sdk
    entered, release, settled = _hold_worker(monkeypatch, manager, phase)
    task = asyncio.create_task(manager.run_workload(workload_id="fixture", input_config=payload,
                                                  workspace=tmp_path, department="core"))
    timeout_owner = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if stop == "cancel":
            task.cancel()
        else:
            timeout_owner = asyncio.create_task(asyncio.wait_for(task, .01))
        # The 0.5-second responsiveness bound is fixed before observing the held worker.
        await asyncio.wait_for(asyncio.sleep(.03), .5)
        assert task.cancelling() == 1
        assert not task.done() and not settled.is_set()
        if stop == "cancel":
            task.cancel()
        release.set()
        with pytest.raises(TimeoutError if stop == "caller-timeout" else asyncio.CancelledError):
            await asyncio.wait_for(timeout_owner or task, 5)
        assert settled.is_set()
        run, attempt, checkpoint, final, effects = await retained_records(tmp_path)
        closed = phase in {"provenance-build", "provenance-write", "digest"}
        assert (final is not None) is closed
        assert run.lifecycle_state.value == ("completed" if closed else "executing")
        assert attempt.attempt_state.value == ("attempt_completed" if closed else "attempt_executing")
        assert len(effects) == (2 if closed else 1)
        assert (tmp_path / "sdk-effect").read_text() == "executed"
    finally:
        release.set()
        if entered.is_set():
            assert await asyncio.to_thread(settled.wait, 5)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, *([timeout_owner] if timeout_owner else []), return_exceptions=True)


async def test_provenance_write_failure_preserves_confirmed_run_and_original_error(tmp_path, admitted_sdk, monkeypatch):
    manager, payload = admitted_sdk
    original = publication_module.write_json_file

    def fail_provenance(path, value):
        if path.name == "provenance.json":
            raise PermissionError("controlled provenance refusal")
        return original(path, value)

    monkeypatch.setattr(publication_module, "write_json_file", fail_provenance)
    with pytest.raises(PermissionError, match="controlled provenance refusal"):
        await manager.run_workload(workload_id="fixture", input_config=payload, workspace=tmp_path, department="core")
    run, attempt, checkpoint, final, effects = await retained_records(tmp_path)
    assert final is not None and len(effects) == 2
    assert run.lifecycle_state.value == "completed"
    assert attempt.attempt_state.value == "attempt_completed"


@pytest.mark.parametrize("phase", ["provenance-build", "provenance-write", "digest"])
async def test_failed_publication_beats_cancellation_and_preserves_final_truth(tmp_path, admitted_sdk, monkeypatch, phase):
    manager, payload = admitted_sdk
    entered, release, settled = _hold_worker(monkeypatch, manager, phase, failure=True)
    task = asyncio.create_task(manager.run_workload(workload_id="fixture", input_config=payload,
                                                  workspace=tmp_path, department="core"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.wait_for(asyncio.sleep(.03), .5)
        assert not task.done()
        task.cancel()
        release.set()
        with pytest.raises(PermissionError, match="controlled held worker refusal"):
            await asyncio.wait_for(task, 5)
        assert settled.is_set()
        run, attempt, checkpoint, final, effects = await retained_records(tmp_path)
        assert final is not None and len(effects) == 2
        assert run.lifecycle_state.value == "completed"
    finally:
        release.set()
        if entered.is_set():
            assert await asyncio.to_thread(settled.wait, 5)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_native_provenance_destination_refusal_preserves_execution(tmp_path, admitted_sdk, monkeypatch):
    manager, payload = admitted_sdk
    original = publication_module.write_json_file

    def occupy_destination(path, value):
        if path.name == "provenance.json":
            path.mkdir()
        return original(path, value)

    monkeypatch.setattr(publication_module, "write_json_file", occupy_destination)
    with pytest.raises(OSError):
        await manager.run_workload(workload_id="fixture", input_config=payload, workspace=tmp_path, department="core")
    run, attempt, checkpoint, final, effects = await retained_records(tmp_path)
    assert final is not None and len(effects) == 2 and run.lifecycle_state.value == "completed"
    assert len(list((tmp_path / "workspace").rglob("artifact_manifest.json"))) == 1
    destination, = (tmp_path / "workspace").rglob("provenance.json")
    assert destination.is_dir()
    assert not list(destination.parent.glob(".*.tmp"))
