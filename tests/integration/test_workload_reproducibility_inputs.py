"""Integration: captured legacy admission and actual Git/material observations."""
from __future__ import annotations

import asyncio
import subprocess

import pytest

from orket.extensions.reproducibility import ReproducibilityEnforcer
from tests.integration.test_workload_publication_inputs import admitted_legacy as admitted_legacy
from tests.integration.test_workload_publication_ownership import _hold_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("setting", ["ORKET_RELIABLE_MODE", "ORKET_RELIABLE_REQUIRE_CLEAN_GIT"])
@pytest.mark.parametrize("admitted", [True, False])
async def test_legacy_admission_captures_policy_before_compile(
    tmp_path, admitted_legacy, monkeypatch, setting, admitted,
):
    manager, payload = admitted_legacy
    # Own the dirty repository; otherwise Git discovers the parent checkout,
    # making this refusal probe pass only while the source worktree is dirty.
    await asyncio.to_thread(subprocess.run, ["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    status = await asyncio.to_thread(subprocess.run, ["git", "status", "--porcelain"],
                                    cwd=tmp_path, check=True, capture_output=True, text=True)
    assert status.stdout.strip(), "The refusal fixture must contain actual untracked files"
    monkeypatch.setenv("ORKET_RELIABLE_MODE", "true")
    monkeypatch.setenv("ORKET_RELIABLE_REQUIRE_CLEAN_GIT", "true")
    monkeypatch.setenv(setting, str(admitted).lower())
    entered, release, settled = _hold_worker(monkeypatch, manager, "compile", legacy=True)
    task = asyncio.create_task(manager.run_workload(workload_id="mystery_v1", input_config=payload,
                                                    workspace=tmp_path, department="core"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        monkeypatch.setenv(setting, str(not admitted).lower())
        release.set()
        if admitted:
            with pytest.raises(RuntimeError, match="(Unable to validate git clean state|requires clean git state)"):
                await asyncio.wait_for(task, 5)
        else:
            result = await asyncio.wait_for(task, 5)
            assert result.summary["ok"]
    finally:
        release.set()
        if entered.is_set():
            assert await asyncio.to_thread(settled.wait, 5)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("state", ["clean", "dirty", "missing"])
async def test_git_clean_guard_observes_real_repository(tmp_path, monkeypatch, state):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    if state != "missing":
        await asyncio.to_thread(subprocess.run, ["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    if state == "dirty":
        await asyncio.to_thread((tmp_path / "untracked.txt").write_text, "dirty", encoding="utf-8")
    guard = ReproducibilityEnforcer(tmp_path)
    if state == "clean":
        await guard.validate_clean_git_if_required(required=True)
    else:
        with pytest.raises(RuntimeError, match="(Unable to validate git clean state|requires clean git state)"):
            await guard.validate_clean_git_if_required(required=True)
    await guard.validate_clean_git_if_required(required=False)


async def test_material_guard_refuses_sibling_with_same_path_prefix(tmp_path):
    root = tmp_path / "project"
    outside = tmp_path / "project-other"
    await asyncio.to_thread(root.mkdir)
    await asyncio.to_thread(outside.mkdir)
    await asyncio.to_thread((outside / "material").write_text, "outside", encoding="utf-8")
    await asyncio.to_thread((root / "material").write_text, "inside", encoding="utf-8")
    guard = ReproducibilityEnforcer(root)
    with pytest.raises(ValueError, match="Material path escapes project root"):
        await asyncio.to_thread(guard.validate_required_materials, ["../project-other/material"])
    await asyncio.to_thread(guard.validate_required_materials, ["material"])
