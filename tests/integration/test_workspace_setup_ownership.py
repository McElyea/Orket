"""Integration: complete canonical setup stages retain actual metadata and file work."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tests.helpers.evidence_ownership import settle_evidence
from tests.helpers.workspace_setup_ownership import (
    FILES,
    assert_closed,
    assert_completed,
    hold_metadata,
    hold_setup_stream,
    interrupt_setup,
    make_stage,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("family,operation,relative", [
    ("scaffolder", "exists", "agent_output/dirs"),
    ("scaffolder", "mkdir", "agent_output/dirs"),
    ("scaffolder", "exists", "agent_output/files/first.txt"),
    ("scaffolder", "is_dir", "agent_output/dirs"),
    ("scaffolder", "is_file", "agent_output/files/first.txt"),
    ("scaffolder", "exists", "agent_output/scan"),
    ("scaffolder", "scan", "agent_output/scan"),
    ("dependency_manager", "exists", "agent_output/dependencies/pyproject.toml"),
    ("dependency_manager", "is_file", "agent_output/dependencies/pyproject.toml"),
    ("deployment_planner", "exists", "agent_output/deployment/first.txt"),
    ("deployment_planner", "is_file", "agent_output/deployment/first.txt"),
])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_complete_setup_retains_each_metadata_phase(
    tmp_path, monkeypatch, record_property, family, operation, relative, mode,
):
    root = tmp_path / "workspace"
    service = await make_stage(family, root)
    hold = hold_metadata(monkeypatch, operation, root / relative)
    task = asyncio.create_task(service.ensure())
    waiter = None
    try:
        waiter = await interrupt_setup(task, hold, mode, tmp_path / "sibling.sqlite3", record_property)
        hold.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        assert_closed(hold)
        await assert_completed(family, root)
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("family", ["scaffolder", "dependency_manager", "deployment_planner"])
@pytest.mark.parametrize("operation", ["open", "write", "close"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_setup_retains_remaining_stage_after_owned_file_operation(
    tmp_path, monkeypatch, record_property, family, operation, mode,
):
    root = tmp_path / "workspace"
    service = await make_stage(family, root)
    hold = hold_setup_stream(monkeypatch, root / FILES[family][0], operation)
    task = asyncio.create_task(service.ensure())
    waiter = None
    try:
        waiter = await interrupt_setup(task, hold, mode, tmp_path / "sibling.sqlite3", record_property)
        hold.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        assert_closed(hold)
        await assert_completed(family, root)
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("family", ["scaffolder", "dependency_manager", "deployment_planner"])
async def test_drive_relative_setup_root_refuses_before_creating_anything(tmp_path, monkeypatch, family):
    if not tmp_path.drive:
        pytest.skip("Windows drive-relative path policy")
    root = tmp_path / "workspace"
    service = await make_stage(family, root)
    monkeypatch.chdir(tmp_path)
    service.workspace_root = Path(tmp_path.drive + "workspace")
    with pytest.raises(ValueError, match="E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED"):
        await service.ensure()
    for name in FILES[family]:
        assert not await asyncio.to_thread((root / name).exists)
