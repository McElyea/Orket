"""Integration: real Git checkouts and catalog publication preserve admitted installations."""
from __future__ import annotations

import asyncio
import json
import subprocess
import threading
from pathlib import Path

import pytest

from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.extensions import installation
from orket.extensions.manager import ExtensionManager
from tests.runtime.test_extension_manager import _init_test_extension_repo

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _source(root):
    root.mkdir()
    _init_test_extension_repo(root)


def _commit(root):
    for args in (["add", "."], ["-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "replacement"]):
        subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)


async def _installed(tmp_path):
    source = tmp_path / "source"
    await asyncio.to_thread(_source, source)
    manager = await asyncio.to_thread(ExtensionManager, catalog_path=tmp_path / "catalog.json", project_root=tmp_path)
    record = await manager.install_from_repo(str(source))
    return source, manager, record


@pytest.mark.parametrize("failure", ["manifest", "reference"])
async def test_failed_replacement_retains_catalog_checkout_and_runnable_workload(tmp_path, failure):
    source, manager, record = await _installed(tmp_path)
    before = await asyncio.to_thread(manager.catalog_path.read_bytes)
    manifest = Path(record.manifest_path)
    admitted = await asyncio.to_thread(manifest.read_bytes)
    if failure == "manifest":
        await asyncio.to_thread((source / "orket_extension.json").write_text, "{malformed", encoding="utf-8")
        await asyncio.to_thread(_commit, source)
    with pytest.raises((ValueError, RuntimeError)):
        await manager.install_from_repo(str(source), ref="does-not-exist" if failure == "reference" else None)
    assert await asyncio.to_thread(manager.catalog_path.read_bytes) == before
    assert await asyncio.to_thread(manifest.read_bytes) == admitted
    await asyncio.to_thread(manager._verify_extension_integrity, record)
    result = await manager.run_workload(workload_id="mystery_v1", input_config={"seed": 7},
                                         workspace=tmp_path / "workspace", department="core")
    assert result.summary["ok"] is True
    assert await asyncio.to_thread(Path(record.path).is_dir)


async def test_successful_replacement_retains_old_checkout_and_publishes_new_record(tmp_path):
    source, manager, old = await _installed(tmp_path)
    new = await manager.install_from_repo(str(source))
    assert new.path != old.path and new.resolved_commit_sha == old.resolved_commit_sha
    payload = json.loads(await asyncio.to_thread(manager.catalog_path.read_text, encoding="utf-8"))
    assert len(payload["extensions"]) == 1 and payload["extensions"][0]["path"] == new.path
    await asyncio.to_thread(manager._verify_extension_integrity, old)
    await asyncio.to_thread(manager._verify_extension_integrity, new)


async def test_missing_git_metadata_cannot_skip_commit_admission(tmp_path):
    _, manager, record = await _installed(tmp_path)
    root = Path(record.path)
    await asyncio.to_thread((root / ".git").rename, root / "retained-git")
    with pytest.raises(RuntimeError, match="E_EXT_REF_RESOLVE_FAILED"):
        await manager.run_workload(workload_id="mystery_v1", input_config={"seed": 7},
                                     workspace=tmp_path / "workspace", department="core")


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_interrupted_manifest_admission_drains_worker_without_publishing(tmp_path, monkeypatch, stop):
    source, manager, record = await _installed(tmp_path)
    before = await asyncio.to_thread(manager.catalog_path.read_bytes)
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = installation._admit_checkout

    def held(**kwargs):
        entered.set()
        try:
            assert release.wait(15)
            return original(**kwargs)
        finally:
            settled.set()

    monkeypatch.setattr(installation, "_admit_checkout", held)
    # Start the timeout after admission is held, so command startup latency cannot hide the worker boundary.
    operation = asyncio.create_task(manager.install_from_repo(str(source)))
    request = operation
    try:
        assert await asyncio.to_thread(entered.wait, 12)
        started = asyncio.get_running_loop().time()
        await asyncio.to_thread((tmp_path / "responsive").write_text, "ready", encoding="utf-8")
        assert asyncio.get_running_loop().time() - started < 0.5
        if stop == "timeout":
            request = asyncio.create_task(asyncio.wait_for(operation, 0.05))
        else:
            operation.cancel()
            await asyncio.sleep(0)
            operation.cancel()
        await asyncio.sleep(0.1)
        assert not request.done() and not settled.is_set()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert isinstance(result, TimeoutError if stop == "timeout" else asyncio.CancelledError)
        assert settled.is_set()
        assert await asyncio.to_thread(manager.catalog_path.read_bytes) == before
        await asyncio.to_thread(manager._verify_extension_integrity, record)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, operation, return_exceptions=True), 5)


async def test_catalog_native_contention_retains_prior_admission(tmp_path):
    source, manager, record = await _installed(tmp_path)
    before = await asyncio.to_thread(manager.catalog_path.read_bytes)
    lock = NativeFileLocks(manager.catalog_path, suffix=".extension-locks",
                           error_prefix="E_EXT_CATALOG", empty_key_error="E_EXT_CATALOG_LOCK_KEY")
    async with lock.hold("catalog"):
        with pytest.raises(ValueError, match="owner_busy"):
            await manager.install_from_repo(str(source))
    assert await asyncio.to_thread(manager.catalog_path.read_bytes) == before
    await asyncio.to_thread(manager._verify_extension_integrity, record)
