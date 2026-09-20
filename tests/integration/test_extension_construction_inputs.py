"""Integration: queued native manager construction retains invocation inputs."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.application.services import extension_catalog_commands as owner

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("catalog_source", ["environment", "default", "explicit"])
@pytest.mark.parametrize("explicit_project", [False, True])
async def test_queued_construction_retains_roots(tmp_path, monkeypatch, catalog_source, explicit_project):
    initial, rotated = tmp_path / "initial", tmp_path / "rotated"
    initial.mkdir()
    rotated.mkdir()
    monkeypatch.chdir(initial)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", "durable-initial")
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", "env.json" if catalog_source == "environment" else "")
    entered, release = asyncio.Event(), asyncio.Event()
    original = owner.run_owned_thread

    async def held(operation, **kwargs):
        entered.set()
        await release.wait()
        return await original(operation, **kwargs)

    monkeypatch.setattr(owner, "run_owned_thread", held)
    task = asyncio.create_task(owner.prepare_extension_manager(
        catalog_path=Path("explicit.json") if catalog_source == "explicit" else None,
        project_root=Path("project") if explicit_project else None))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        monkeypatch.chdir(rotated)
        monkeypatch.setenv("ORKET_DURABLE_ROOT", "durable-rotated")
        monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", "rotated.json")
        release.set()
        manager = await asyncio.wait_for(task, 5)
        catalog = {"environment": "env.json", "explicit": "explicit.json",
                   "default": "durable-initial/config/extensions_catalog.json"}[catalog_source]
        project = initial / "project" if explicit_project else initial
        assert manager.catalog_path == initial / catalog
        assert manager.project_root == project
        assert manager.install_root == initial / "durable-initial/extensions"
        assert (project / ".orket/durable/db").is_dir()
        assert not list(rotated.iterdir())
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_explicit_environment_is_captured_before_worker_scheduling(tmp_path, monkeypatch):
    selected = {"ORKET_DURABLE_ROOT": "selected", "ORKET_EXTENSIONS_CATALOG": "selected.json"}
    original = owner.run_owned_thread

    async def rotate_then_run(operation, **kwargs):
        selected.update(ORKET_DURABLE_ROOT="late", ORKET_EXTENSIONS_CATALOG="late.json")
        return await original(operation, **kwargs)

    monkeypatch.setattr(owner, "run_owned_thread", rotate_then_run)
    manager = await owner.prepare_extension_manager(environment=selected, invocation_root=tmp_path)
    assert manager.install_root == tmp_path / "selected/extensions"
    assert manager.catalog_path == tmp_path / "selected.json"
    assert manager.project_root == tmp_path
    assert (tmp_path / ".orket/durable/db").is_dir()


async def test_relative_invocation_root_is_refused_without_publication(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="E_EXT_INVOCATION_ROOT_ABSOLUTE_REQUIRED"):
        await owner.prepare_extension_manager(invocation_root=Path("relative"))
    assert not list(tmp_path.iterdir())
