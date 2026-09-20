"""Integration: direct preparation retains native workers and captured locations."""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
import threading
import time
from functools import partial
from pathlib import Path

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services import extension_workload_composition as composition
from orket.application.services.extension_catalog_commands import prepare_extension_manager
from orket.extensions.manager import ExtensionManager

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def construction(kind, root):
    if kind == "manager":
        return partial(
            ExtensionManager,
            catalog_path=root / "catalog.json",
            project_root=root,
            invocation_root=root,
            environment={},
        )
    return partial(composition.build_extension_workload_control_plane_service, project_root=root)


async def preparation(kind, root):
    if kind == "manager":
        return await prepare_extension_manager(project_root=root, invocation_root=root, environment={})
    return await composition.prepare_extension_workload_control_plane_service(project_root=root, invocation_root=root)


@pytest.mark.parametrize("kind", ["manager", "control-plane"])
async def test_direct_loop_construction_refuses_before_effects(tmp_path, kind):
    with pytest.raises(RuntimeError, match="REQUIRES_WORKER"):
        construction(kind, tmp_path)()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ["manager", "control-plane"])
async def test_worker_construction_reaches_native_storage(tmp_path, kind):
    constructed = await run_owned_thread(construction(kind, tmp_path), label="direct-manager-positive-control")
    service = constructed.workload_executor.control_plane if kind == "manager" else constructed
    assert (tmp_path / ".orket/durable/db").is_dir()
    assert await service.execution_repository.get_run_record(run_id="absent") is None
    assert (tmp_path / ".orket/durable/db/control_plane_records.sqlite3").is_file()


@pytest.mark.parametrize("kind", ["manager", "control-plane"])
@pytest.mark.parametrize("stop", ["complete", "cancel", "caller-timeout"])
@pytest.mark.parametrize("refuse", [False, True])
async def test_preparation_retains_native_worker(tmp_path, monkeypatch, kind, stop, refuse):
    target = tmp_path / ".orket/durable/db"
    if refuse:
        await asyncio.to_thread((tmp_path / ".orket").write_text, "native obstruction", encoding="utf-8")
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
    task = asyncio.create_task(preparation(kind, tmp_path))
    timeout_owner = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if stop == "cancel":
            task.cancel()
        elif stop == "caller-timeout":
            timeout_owner = asyncio.create_task(asyncio.wait_for(task, 0.01))
        started = time.monotonic()
        await asyncio.sleep(0.03)
        # Declared before execution; injected holds are not natural filesystem latency.
        assert time.monotonic() - started < 0.5
        assert not task.done() and not settled.is_set()
        if stop != "complete":
            assert task.cancelling() == 1
            task.cancel()
        release.set()
        owned = timeout_owner or task
        if refuse:
            with pytest.raises(OSError):
                await asyncio.wait_for(owned, 10)
        elif stop != "complete":
            with pytest.raises(TimeoutError if timeout_owner else asyncio.CancelledError):
                await asyncio.wait_for(owned, 10)
        else:
            await asyncio.wait_for(owned, 10)
        assert settled.is_set()
        assert target.is_dir() is (not refuse)
        assert not (target / "control_plane_records.sqlite3").exists()
    finally:
        release.set()
        await asyncio.gather(task, *([timeout_owner] if timeout_owner else []), return_exceptions=True)


@pytest.mark.parametrize("explicit_database", [False, True])
async def test_queued_control_plane_preparation_retains_relative_locations(tmp_path, monkeypatch, explicit_database):
    initial, rotated = tmp_path / "initial", tmp_path / "rotated"
    initial.mkdir()
    rotated.mkdir()
    monkeypatch.chdir(initial)
    entered, release = asyncio.Event(), asyncio.Event()
    original = composition.run_owned_thread

    async def held(operation, **kwargs):
        entered.set()
        await release.wait()
        return await original(operation, **kwargs)

    monkeypatch.setattr(composition, "run_owned_thread", held)
    task = asyncio.create_task(
        composition.prepare_extension_workload_control_plane_service(
            project_root=Path("project"), db_path=Path("selected/db.sqlite3") if explicit_database else None
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        monkeypatch.chdir(rotated)
        release.set()
        service = await asyncio.wait_for(task, 5)
        database = initial / (
            "selected/db.sqlite3" if explicit_database else "project/.orket/durable/db/control_plane_records.sqlite3"
        )
        assert await service.execution_repository.get_run_record(run_id="absent") is None
        assert database.is_file()
        assert Path(service.execution_repository.db_path) == database
        assert Path(service.publication.repository.db_path) == database
        assert Path(service.transactions.db_path) == database
        assert list(rotated.iterdir()) == []
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_control_plane_relative_invocation_root_refuses_without_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="E_EXT_INVOCATION_ROOT_ABSOLUTE_REQUIRED"):
        await composition.prepare_extension_workload_control_plane_service(
            project_root=Path("project"), invocation_root=Path("relative")
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("explicit_database", [False, True])
async def test_sync_preparation_retains_relative_database(tmp_path, monkeypatch, explicit_database):
    initial, rotated = tmp_path / "initial", tmp_path / "rotated"
    initial.mkdir()
    rotated.mkdir()
    monkeypatch.chdir(initial)
    service = await asyncio.to_thread(
        composition.build_extension_workload_control_plane_service,
        project_root=Path("project"),
        db_path=Path("selected/db.sqlite3") if explicit_database else None,
    )
    monkeypatch.chdir(rotated)
    assert await service.execution_repository.get_run_record(run_id="absent") is None
    selected = initial / (
        "selected/db.sqlite3" if explicit_database else "project/.orket/durable/db/control_plane_records.sqlite3"
    )
    assert selected.is_file()
    assert Path(service.execution_repository.db_path) == selected
    assert list(rotated.iterdir()) == []


def create_competing_store(other):
    other.parent.mkdir(parents=True)
    with sqlite3.connect(other) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('retained')")
    return hashlib.sha256(other.read_bytes()).hexdigest()


def verify_competing_store(other, before):
    assert hashlib.sha256(other.read_bytes()).hexdigest() == before
    with sqlite3.connect(other) as connection:
        assert connection.execute("SELECT value FROM sentinel").fetchall() == [("retained",)]
        assert connection.execute("SELECT name FROM sqlite_master WHERE name LIKE 'control_plane_%'").fetchall() == []


@pytest.mark.parametrize("explicit_database", [False, True])
async def test_sync_preparation_leaves_competing_store_unchanged(tmp_path, monkeypatch, explicit_database):
    initial, rotated = tmp_path / "initial", tmp_path / "rotated"
    initial.mkdir()
    relative = Path(
        "selected/db.sqlite3" if explicit_database else "project/.orket/durable/db/control_plane_records.sqlite3"
    )
    other = rotated / relative
    before = await asyncio.to_thread(create_competing_store, other)
    monkeypatch.chdir(initial)
    service = await asyncio.to_thread(
        composition.build_extension_workload_control_plane_service,
        project_root=Path("project"),
        db_path=relative if explicit_database else None,
    )
    monkeypatch.chdir(rotated)
    assert await service.execution_repository.get_run_record(run_id="absent") is None
    assert (initial / relative).is_file()
    await asyncio.to_thread(verify_competing_store, other, before)
