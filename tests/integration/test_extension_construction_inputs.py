"""Integration: queued native manager construction retains invocation inputs."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.application.services import extension_catalog_commands as owner
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
@pytest.mark.parametrize("catalog_source", ["environment", "default", "explicit"])
@pytest.mark.parametrize("explicit_project", [False, True])
async def test_legacy_queued_construction_selects_roots_at_worker_start(
    tmp_path, monkeypatch, catalog_source, explicit_project,
):
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
        rotated_catalog = "rotated.json" if catalog_source != "default" else ""
        monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", rotated_catalog)
        release.set()
        manager = await asyncio.wait_for(task, 5)
        catalog = {"environment": "rotated.json", "explicit": "explicit.json",
                   "default": "durable-rotated/config/extensions_catalog.json"}[catalog_source]
        project = rotated / "project" if explicit_project else rotated
        assert manager.catalog_path == rotated / catalog
        assert manager.project_root == project
        assert manager.install_root == rotated / "durable-rotated/extensions"
        assert (project / ".orket/durable/db").is_dir()
        assert not list(initial.iterdir())
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


# Layer: integration
async def test_legacy_environment_is_captured_at_worker_start(tmp_path, monkeypatch):
    selected = {"ORKET_DURABLE_ROOT": "selected", "ORKET_EXTENSIONS_CATALOG": "selected.json"}
    original = owner.run_owned_thread

    async def rotate_then_run(operation, **kwargs):
        selected.update(ORKET_DURABLE_ROOT="late", ORKET_EXTENSIONS_CATALOG="late.json")
        return await original(operation, **kwargs)

    monkeypatch.setattr(owner, "run_owned_thread", rotate_then_run)
    manager = await owner.prepare_extension_manager(environment=selected, invocation_root=tmp_path)
    assert manager.install_root == tmp_path / "late/extensions"
    assert manager.catalog_path == tmp_path / "late.json"
    assert manager.project_root == tmp_path
    assert (tmp_path / ".orket/durable/db").is_dir()


# Layer: integration
async def test_selected_full_inputs_drive_extension_construction_without_recapture(tmp_path, monkeypatch):
    selected = RuntimeConstructionInputs(
        tmp_path.resolve(),
        {"ORKET_DURABLE_ROOT": "selected", "ORKET_EXTENSIONS_CATALOG": "selected.json"},
        "{}", "{}",
    )
    monkeypatch.setenv("ORKET_DURABLE_ROOT", "ambient")
    manager = await owner.prepare_extension_manager(construction_inputs=selected)
    assert manager.install_root == tmp_path / "selected/extensions"
    assert manager.catalog_path == tmp_path / "selected.json"
    assert manager.project_root == tmp_path
    assert manager._construction_inputs is selected
    assert manager.workload_executor._construction_inputs is selected
    with pytest.raises(ValueError, match="^E_EXTENSION_CONSTRUCTION_INPUTS_AMBIGUOUS$"):
        await owner.prepare_extension_manager(
            construction_inputs=selected, environment={"AMBIGUOUS": "1"})


# Layer: integration
async def test_relative_invocation_root_is_refused_without_publication(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="E_EXT_INVOCATION_ROOT_ABSOLUTE_REQUIRED"):
        await owner.prepare_extension_manager(invocation_root=Path("relative"))
    assert not list(tmp_path.iterdir())
