"""Integration: each actual workload keeps its admitted policy across environment rotation."""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.extensions.workload_policy import capture_workload_policy
from orket_extension_sdk.result import ArtifactRef, WorkloadResult
from tests.integration.test_sdk_process_control_plane import admitted_sdk as admitted_sdk
from tests.integration.test_workload_publication_inputs import admitted_legacy as admitted_legacy
from tests.integration.test_workload_publication_ownership import _hold_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _select_policy(monkeypatch, *, rotated):
    values = {
        "ORKET_RELIABLE_MODE": "false" if rotated else "true",
        "ORKET_RELIABLE_REQUIRE_CLEAN_GIT": "true" if rotated else "false",
        "ORKET_EXT_PROVENANCE_VERBOSE": "true" if rotated else "false",
        "ORKET_EXT_ARTIFACT_FILE_SIZE_CAP_BYTES": "2097152" if rotated else "1048576",
        "ORKET_EXT_ARTIFACT_TOTAL_SIZE_CAP_BYTES": "4194304" if rotated else "2097152",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


async def _read_json(path):
    return json.loads(await asyncio.to_thread(Path(path).read_text, encoding="utf-8"))


@pytest.mark.parametrize("family", ["sdk", "legacy"])
async def test_policy_rotation_keeps_admitted_result_manifest_and_provenance(
    tmp_path, admitted_sdk, admitted_legacy, monkeypatch, family,
):
    manager, payload = admitted_sdk if family == "sdk" else admitted_legacy
    _select_policy(monkeypatch, rotated=False)
    entered, release, settled = _hold_worker(monkeypatch, manager, "manifest-build", legacy=family == "legacy")
    workload_id = "fixture" if family == "sdk" else "mystery_v1"
    task = asyncio.create_task(manager.run_workload(workload_id=workload_id, input_config=payload,
                                                  workspace=tmp_path, department="core"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        _select_policy(monkeypatch, rotated=True)
        release.set()
        result = await asyncio.wait_for(task, 5)
        provenance = await _read_json(result.provenance_path)
        manifest = await _read_json(result.artifact_manifest_path)
        assert result.policy_digest == provenance["policy_digest"] == manifest["policy_digest"]
        assert result.control_bundle_hash == provenance["control_bundle_hash"] == manifest["control_bundle_hash"]
        assert provenance["reliable_mode"] is True
        assert provenance["input_config"] == {}
        records = AsyncControlPlaneExecutionRepository(tmp_path / ".orket/durable/db/control_plane_records.sqlite3")
        run = await records.get_run_record(run_id=result.control_plane["control_plane_run_id"])
        assert run.policy_digest == result.policy_digest
        # Reuse the same manager: policy capture belongs to invocation, not construction.
        second = await manager.run_workload(workload_id=workload_id, input_config={**payload, "seed": 43},
                                            workspace=tmp_path, department="core")
        second_provenance = await _read_json(second.provenance_path)
        assert second.policy_digest != result.policy_digest
        assert second_provenance["policy_digest"] == second.policy_digest
        assert second_provenance["reliable_mode"] is False
        assert second_provenance["input_config"]
    finally:
        release.set()
        if entered.is_set():
            assert await asyncio.to_thread(settled.wait, 5)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("family", ["sdk", "legacy"])
@pytest.mark.parametrize("limit", ["FILE", "TOTAL"])
@pytest.mark.parametrize("admitted_cap", [8, 32])
async def test_manifest_enforces_admitted_size_cap_after_environment_rotation(
    tmp_path, admitted_sdk, admitted_legacy, monkeypatch, family, limit, admitted_cap,
):
    manager, payload = admitted_sdk if family == "sdk" else admitted_legacy
    key = f"ORKET_EXT_ARTIFACT_{limit}_SIZE_CAP_BYTES"
    _select_policy(monkeypatch, rotated=False)
    monkeypatch.setenv(key, str(admitted_cap))
    artifacts = manager.workload_executor.artifacts
    original = artifacts.build_artifact_manifest
    entered, release = threading.Event(), threading.Event()

    def held(root, **kwargs):
        # Actual emitted file, observed by the production manifest validator.
        (root / "size-fixture.bin").write_bytes(b"x" * 16)
        entered.set()
        if not release.wait(10):
            raise RuntimeError("manifest worker was not released")
        return original(root, **kwargs)

    monkeypatch.setattr(artifacts, "build_artifact_manifest", held)
    task = asyncio.create_task(manager.run_workload(workload_id="fixture" if family == "sdk" else "mystery_v1",
        input_config=payload, workspace=tmp_path, department="core"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        monkeypatch.setenv(key, "32" if admitted_cap == 8 else "8")
        release.set()
        if admitted_cap == 8:
            with pytest.raises(ValueError, match=f"E_ARTIFACT_{limit}_SIZE_CAP"):
                await asyncio.wait_for(task, 5)
        else:
            result = await asyncio.wait_for(task, 5)
            manifest = await _read_json(result.artifact_manifest_path)
            assert [row["path"] for row in manifest["files"]] == ["size-fixture.bin"]
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("family", ["sdk", "legacy"])
async def test_overlapping_invocations_on_same_manager_keep_distinct_policies(
    tmp_path, admitted_sdk, admitted_legacy, monkeypatch, family,
):
    manager, payload = admitted_sdk if family == "sdk" else admitted_legacy
    _select_policy(monkeypatch, rotated=False)
    artifacts = manager.workload_executor.artifacts
    original = artifacts.build_artifact_manifest
    entered, release = threading.Event(), threading.Event()

    def held(root, **kwargs):
        if "-41-" in root.name:
            entered.set()
            if not release.wait(10):
                raise RuntimeError("manifest worker was not released")
        return original(root, **kwargs)

    monkeypatch.setattr(artifacts, "build_artifact_manifest", held)
    workload_id = "fixture" if family == "sdk" else "mystery_v1"
    first = asyncio.create_task(manager.run_workload(workload_id=workload_id, input_config={**payload, "seed": 41},
                                                    workspace=tmp_path, department="core"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        _select_policy(monkeypatch, rotated=True)
        second = await asyncio.wait_for(manager.run_workload(workload_id=workload_id,
            input_config={**payload, "seed": 42}, workspace=tmp_path, department="core"), 5)
        assert not first.done()
        release.set()
        first_result = await asyncio.wait_for(first, 5)
        for result, reliable, verbose in [(first_result, True, False), (second, False, True)]:
            provenance = await _read_json(result.provenance_path)
            assert provenance["policy_digest"] == result.policy_digest
            assert provenance["reliable_mode"] is reliable
            assert bool(provenance["input_config"]) is verbose
        assert first_result.policy_digest != second.policy_digest
    finally:
        release.set()
        if not first.done():
            first.cancel()
        await asyncio.gather(first, return_exceptions=True)


@pytest.mark.parametrize("limit", ["FILE", "TOTAL"])
@pytest.mark.parametrize("admitted_cap", [8, 32])
async def test_sdk_declared_artifact_validation_uses_captured_cap(tmp_path, admitted_sdk, monkeypatch, limit, admitted_cap):
    manager, _ = admitted_sdk
    _select_policy(monkeypatch, rotated=False)
    key = f"ORKET_EXT_ARTIFACT_{limit}_SIZE_CAP_BYTES"
    monkeypatch.setenv(key, str(admitted_cap))
    policy = capture_workload_policy()
    data = b"x" * 16
    await asyncio.to_thread((tmp_path / "declared.bin").write_bytes, data)
    result = WorkloadResult(ok=True, artifacts=[
        ArtifactRef(path="declared.bin", digest_sha256=hashlib.sha256(data).hexdigest(), kind="bin")])
    monkeypatch.setenv(key, "32" if admitted_cap == 8 else "8")
    validation = asyncio.to_thread(manager.workload_executor.artifacts.validate_sdk_artifacts,
                                    result, tmp_path, policy=policy)
    if admitted_cap == 8:
        with pytest.raises(ValueError, match=f"E_ARTIFACT_{limit}_SIZE_CAP"):
            await validation
    else:
        await validation
