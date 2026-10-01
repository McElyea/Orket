"""Integration: capture supported setup inputs and retain native/validation failure truth."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import orket.application.services.epic_setup_service as epic_setup
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.orchestrator_support_services import OrchestratorSupportServices
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from tests.helpers.evidence_ownership import settle_evidence
from tests.helpers.runtime_verification_hold import wait_entered
from tests.helpers.workspace_setup_ownership import (
    FILES,
    VALIDATION_ERRORS,
    assert_closed,
    assert_completed,
    first_boundary,
    hold_metadata,
    interrupt_setup,
    make_stage,
    prepare_tree,
    setup_rules,
    tree_contents,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("family", ["scaffolder", "dependency_manager", "deployment_planner"])
async def test_setup_retains_selected_root_tools_and_resolved_spec(tmp_path, monkeypatch, family):
    root, other = tmp_path / "workspace", tmp_path / "changed"
    service = await make_stage(family, root)
    hold = hold_metadata(monkeypatch, "exists", root / first_boundary(family))
    task = asyncio.create_task(service.ensure())
    try:
        await wait_entered(hold)
        service.workspace_root = other
        service.file_tools.workspace_root = other
        service.file_tools.references.append(other)
        service.file_tools = AsyncFileTools(other)
        service.organization.process_rules.clear()
        service.project_surface_profile = "api_vue"
        service.architecture_pattern = "microservices"
        hold.release.set()
        result = await task
        assert result["required_files"] == sorted(FILES[family])
        assert_closed(hold)
        await assert_completed(family, root)
        assert not await asyncio.to_thread(other.exists)
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("family", ["scaffolder", "dependency_manager", "deployment_planner"])
async def test_relative_setup_binds_before_cwd_changes(tmp_path, monkeypatch, family):
    first, changed = tmp_path / "first", tmp_path / "changed"
    root, other = first / "workspace", changed / "workspace"
    service = await make_stage(family, root)
    await asyncio.to_thread(prepare_tree, other, scan=False)
    service.workspace_root = service.file_tools.workspace_root = Path("workspace")
    monkeypatch.chdir(first)
    hold = hold_metadata(monkeypatch, "exists", Path(first_boundary(family)), suffix=True)
    task = asyncio.create_task(service.ensure())
    try:
        await wait_entered(hold)
        monkeypatch.chdir(changed)
        hold.release.set()
        await task
        assert_closed(hold)
        await assert_completed(family, root)
        assert await asyncio.to_thread(tree_contents, other) == {}
    finally:
        monkeypatch.chdir(first)
        await settle_evidence(task, hold)


@pytest.mark.parametrize("family", ["scaffolder", "dependency_manager", "deployment_planner"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_setup_preserves_native_failure_identity_after_interruption(
    tmp_path, monkeypatch, record_property, family, mode,
):
    root = tmp_path / "workspace"
    service = await make_stage(family, root)
    before = await asyncio.to_thread(tree_contents, root)
    failure = OSError("controlled setup metadata acknowledgement failure")
    hold = hold_metadata(monkeypatch, "exists", root / first_boundary(family), failure=failure)
    task = asyncio.create_task(service.ensure())
    waiter = None
    try:
        waiter = await interrupt_setup(task, hold, mode, tmp_path / "sibling.sqlite3", record_property)
        hold.release.set()
        with pytest.raises(OSError) as observed:
            await waiter
        assert observed.value is failure
        assert_closed(hold)
        assert await asyncio.to_thread(tree_contents, root) == before
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("family", ["scaffolder", "dependency_manager", "deployment_planner"])
async def test_setup_validation_failure_preserves_prior_files_and_original_exception(
    tmp_path, monkeypatch, record_property, family,
):
    root = tmp_path / "workspace"
    service = await make_stage(family, root)
    collision = root / FILES[family][1]
    await asyncio.to_thread(collision.mkdir, parents=True)
    hold = hold_metadata(monkeypatch, "is_file", collision)
    task = asyncio.create_task(service.ensure())
    try:
        await interrupt_setup(task, hold, "cancel", tmp_path / "sibling.sqlite3", record_property)
        hold.release.set()
        with pytest.raises(VALIDATION_ERRORS[family], match="missing .*files"):
            await task
        assert_closed(hold)
        assert await asyncio.to_thread((root / FILES[family][0]).is_file)
        assert await asyncio.to_thread(collision.is_dir)
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_epic_setup_stops_between_complete_stages_after_interruption(
    tmp_path, monkeypatch, record_property, mode,
):
    root = tmp_path / "workspace"
    await asyncio.to_thread(prepare_tree, root)
    support, observed = OrchestratorSupportServices(), []
    monkeypatch.setattr(support, "load_user_settings", lambda: {})
    monkeypatch.setattr(epic_setup, "log_event", lambda name, *_args: observed.append(name))
    for name in ("SCAFFOLDER", "DEPENDENCY_MANAGER", "DEPLOYMENT_PLANNER"):
        monkeypatch.setenv("ORKET_DISABLE_" + name, "false")
    monkeypatch.setenv("ORKET_PROJECT_SURFACE_PROFILE", "unspecified")
    owner = SimpleNamespace(workspace=root, org=SimpleNamespace(process_rules=setup_rules()),
        support_services=support, architecture_policy=ArchitecturePolicySnapshot(False), decision_environment={})
    hold = hold_metadata(monkeypatch, "exists", root / "agent_output/dirs")
    task = asyncio.create_task(epic_setup.prepare_epic_workspace(owner, SimpleNamespace(name="owned-setup"), "run"))
    waiter = None
    try:
        waiter = await interrupt_setup(task, hold, mode, tmp_path / "sibling.sqlite3", record_property)
        hold.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        assert_closed(hold)
        await assert_completed("scaffolder", root)
        assert observed == ["scaffolder_started"]
    finally:
        await settle_evidence(task, hold)
