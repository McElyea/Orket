"""Integration: missing SDK observations cannot become terminal no-effect truth."""
from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.extensions.controller_dispatcher import ControllerDispatcher
from orket.extensions.manager import ExtensionManager
from orket.extensions.sdk_workload_runner import SdkSubprocessExecutionUncertain, SdkSubprocessRunError
from orket_extension_sdk.controller import ControllerPolicyCaps
from tests.helpers.sdk_lifetime import owned_fixture_processes, sdk_request
from tests.integration.test_verification_process_lifetime import assert_stopped, await_tree, stop_observed

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def admitted_sdk(tmp_path):
    options = sdk_request(tmp_path)
    extension, workload = options["extension"], options["workload"]
    root = Path(extension.path)
    (root / "extension.json").write_text(json.dumps({"manifest_version": "v0",
        "extension_id": extension.extension_id, "extension_version": "1.0.0",
        "allowed_stdlib_modules": list(extension.allowed_stdlib_modules),
        "workloads": [{"workload_id": workload.workload_id, "entrypoint": workload.entrypoint,
                       "required_capabilities": []}]}), encoding="utf-8")
    for args in [["init"], ["add", "."], ["-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "fixture"]]:
        subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
    manager = ExtensionManager(catalog_path=tmp_path / "catalog.json", project_root=tmp_path)
    asyncio.run(manager.install_from_repo(str(root)))
    return manager, options["input_payload"]


async def retained_records(root):
    run_id = await asyncio.to_thread((root / "sdk-run-id").read_text)
    db = root / ".orket" / "durable" / "db" / "control_plane_records.sqlite3"
    executions = AsyncControlPlaneExecutionRepository(db)
    records = AsyncControlPlaneRecordRepository(db)
    run = await executions.get_run_record(run_id=run_id)
    attempts = await executions.list_attempt_records(run_id=run_id)
    assert run is not None and len(attempts) == 1
    checkpoint = await records.get_checkpoint(checkpoint_id=f"extension-workload-checkpoint:{attempts[0].attempt_id}")
    assert checkpoint is not None
    assert checkpoint.resumability_class.value == "resume_forbidden"
    final = await records.get_final_truth(run_id=run_id)
    effects = await records.list_effect_journal_entries(run_id=run_id)
    return run, attempts[0], checkpoint, final, effects


@pytest.mark.parametrize("mode", ["missing", "output-limit", "success", "error"])
async def test_manager_retains_unknown_sdk_effects_without_final_truth(tmp_path, admitted_sdk, monkeypatch, mode):
    exchanges = tmp_path / "exchanges"
    exchanges.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(exchanges))
    manager, payload = admitted_sdk
    payload["mode"] = mode
    request = manager.run_workload(workload_id="fixture", input_config=payload, workspace=tmp_path, department="core")
    if mode in {"missing", "output-limit"}:
        with pytest.raises(SdkSubprocessExecutionUncertain) as caught:
            await asyncio.wait_for(request, 15)
        assert caught.value.lifetime.cleanup_confirmed
        assert caught.value.exchange_path.is_dir()
        assert caught.value.phase == ("result-read" if mode == "missing" else "native-output_limit")
    elif mode == "error":
        with pytest.raises(SdkSubprocessRunError, match="controlled workload failure"):
            await asyncio.wait_for(request, 15)
        assert not list(exchanges.iterdir())
    else:
        result = await asyncio.wait_for(request, 15)
        assert result.summary["ok"] is (mode == "success")
        assert not list(exchanges.iterdir())
    run, attempt, checkpoint, final, effects = await retained_records(tmp_path)
    assert (tmp_path / "sdk-effect").read_text() == "executed"
    if mode in {"missing", "output-limit"}:
        assert final is None
        assert run.lifecycle_state.value == "executing"
        assert attempt.attempt_state.value == "attempt_executing"
        assert len(effects) == 1
    else:
        assert final is not None
        assert attempt.attempt_state.value == ("attempt_completed" if mode == "success" else "attempt_failed")
        assert len(effects) == 2


async def test_manager_cancellation_retains_unresolved_run_after_native_cleanup(tmp_path, admitted_sdk):
    manager, payload = admitted_sdk
    payload.update(tree=True, flags=["detached", "ignore-term"])
    task = asyncio.create_task(manager.run_workload(workload_id="fixture", input_config=payload,
                                                  workspace=tmp_path, department="core"))
    processes = []
    try:
        await await_tree(tmp_path)
        processes = await asyncio.to_thread(owned_fixture_processes, tmp_path)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        await assert_stopped(processes, tmp_path)
        run, attempt, checkpoint, final, effects = await retained_records(tmp_path)
        assert final is None and len(effects) == 1
        assert run.lifecycle_state.value == "executing"
        assert attempt.attempt_state.value == "attempt_executing"
    finally:
        if not processes:
            processes = await asyncio.to_thread(owned_fixture_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_controller_deadline_returns_failure_after_native_cleanup(tmp_path, admitted_sdk):
    manager, payload = admitted_sdk
    payload.update(tree=True, flags=["detached", "ignore-term"])
    dispatcher = ControllerDispatcher(extension_manager=manager,
        runtime_policy_caps=ControllerPolicyCaps(max_depth=1, max_fanout=5, child_timeout_seconds=5))
    request = {"controller_contract_version": "controller.workload.v1", "controller_workload_id": "controller",
        "parent_depth": 0, "ancestry": [], "children": [{"target_workload": "fixture", "contract_style": "sdk_v0",
                                                        "timeout_seconds": 5, "payload": payload}]}
    task = asyncio.create_task(dispatcher.dispatch(payload=request, workspace=tmp_path, department="core"))
    processes = []
    try:
        await await_tree(tmp_path)
        processes = await asyncio.to_thread(owned_fixture_processes, tmp_path)
        summary = await asyncio.wait_for(asyncio.shield(task), 10)
        assert summary.status == "failed"
        assert summary.error_code == "controller.child_execution_failed"
        assert [row.status for row in summary.child_results] == ["failed"]
        await assert_stopped(processes, tmp_path)
        run, attempt, checkpoint, final, effects = await retained_records(tmp_path)
        assert final is None and len(effects) == 1
        assert run.lifecycle_state.value == "executing"
        assert attempt.attempt_state.value == "attempt_executing"
    finally:
        if not processes:
            processes = await asyncio.to_thread(owned_fixture_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
