"""Public model preparation binds real score reads to its invocation directory."""
import asyncio
from pathlib import Path

import pytest

from orket.application.services.model_selection_service import ModelSelectionService
from orket.settings import set_runtime_settings_context
from tests.helpers.model_score_root import (
    assert_observation,
    assert_selection,
    entered,
    hold_preparation,
    score_settings,
    seed_roots,
    settle,
)
from tests.helpers.runtime_verification_hold import sqlite_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("phase", ["preferences", "settings", "scores"])
@pytest.mark.parametrize("absolute", [False, True], ids=["relative", "absolute"])
async def test_score_root_precedes_each_settings_or_score_wait(tmp_path, monkeypatch, record_property, phase, absolute):
    original, later, raw = await asyncio.to_thread(seed_roots, tmp_path)
    settings = score_settings(original / "scores.json" if absolute else "scores.json")
    set_runtime_settings_context(user_settings=settings, user_preferences={})
    owner = ModelSelectionService(environment={"ORKET_MODEL_CODER": "candidate"})
    monkeypatch.chdir(original)
    hold = hold_preparation(monkeypatch, "model-selection-" + phase)
    task = asyncio.create_task(owner.prepare(preferences=None if phase == "preferences" else {},
        user_settings=None if phase == "settings" else settings))
    try:
        await entered(hold)
        assert not hold.observations, "score bytes were observed before the controlled hold"
        monkeypatch.chdir(later)
        settings["model_compliance_policy"]["fallback_model"] = "later-fallback"
        assert await sqlite_response(tmp_path / "responsive.sqlite3", record_property) < 0.5
        assert not task.done()
        hold.release.set()
        prepared = await asyncio.wait_for(task, 5)
        assert_selection(prepared, original, raw)
        assert hold.score_calls == [str(original / "scores.json")]
        assert len(hold.observations) == 1
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("interruption", ["cancel", "timeout"])
async def test_held_relative_score_read_settles_before_interruption(tmp_path, monkeypatch, record_property, interruption):
    original, later, raw = await asyncio.to_thread(seed_roots, tmp_path)
    monkeypatch.chdir(original)
    hold = hold_preparation(monkeypatch, "model-selection-scores")
    task = asyncio.create_task(ModelSelectionService(environment={"ORKET_MODEL_CODER": "candidate"}).prepare(
        preferences={}, user_settings=score_settings("scores.json")))
    waiter = task
    try:
        await entered(hold)
        monkeypatch.chdir(later)
        if interruption == "cancel":
            task.cancel("first interruption")
            await asyncio.sleep(0)
            task.cancel("repeated interruption")
        else:
            waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
        await asyncio.sleep(0.04)
        assert await sqlite_response(tmp_path / "responsive.sqlite3", record_property) < 0.5
        assert not task.done() and not waiter.done() and not hold.finished.is_set()
        assert not hold.observations
        hold.release.set()
        with pytest.raises(asyncio.CancelledError if interruption == "cancel" else TimeoutError):
            await waiter
        assert hold.finished.is_set() and len(hold.observations) == 1
        assert_observation(hold.observations[0], original, raw)
        assert hold.score_calls == [str(original / "scores.json")]
    finally:
        await settle(task, hold)
        await asyncio.gather(waiter, return_exceptions=True)


@pytest.mark.parametrize("status", ["missing", "invalid", "partial", "unavailable"])
async def test_score_failure_uses_selected_root_without_adopting_other_directory(tmp_path, monkeypatch, caplog, status):
    original, later, raw = await asyncio.to_thread(seed_roots, tmp_path, status)
    monkeypatch.chdir(original)
    set_runtime_settings_context(user_preferences={})
    hold = hold_preparation(monkeypatch, "model-selection-preferences")
    task = asyncio.create_task(ModelSelectionService(environment={"ORKET_MODEL_CODER": "candidate"}).prepare(
        user_settings=score_settings("scores.json")))
    try:
        await entered(hold)
        monkeypatch.chdir(later)
        hold.release.set()
        prepared = await asyncio.wait_for(task, 5)
        assert_selection(prepared, original, raw, status)
        assert hold.score_calls == [str(original / "scores.json")]
        assert "Model selection score report " + status in caplog.text
    finally:
        await settle(task, hold)


async def test_root_is_selected_per_preparation_not_service_construction(tmp_path, monkeypatch):
    original, later, raw = await asyncio.to_thread(seed_roots, tmp_path)
    monkeypatch.chdir(later)
    owner = ModelSelectionService(environment={"ORKET_MODEL_CODER": "candidate"})
    settings = score_settings("scores.json")
    monkeypatch.chdir(original)
    first = await owner.prepare(preferences={}, user_settings=settings)
    monkeypatch.chdir(later)
    second = await owner.prepare(preferences={}, user_settings=settings)
    assert_selection(first, original, raw)
    selected = second.select("coder")
    assert selected.final_model == "candidate" and selected.reason == "score_ok" and selected.score == 99
    assert selected.score_source.path == str(later / "scores.json")
    assert selected.score_source.sha256 != first.select("coder").score_source.sha256


async def test_drive_relative_report_uses_canonical_native_path_admission(tmp_path, monkeypatch):
    original, _later, raw = await asyncio.to_thread(seed_roots, tmp_path)
    monkeypatch.chdir(original)
    source = original.drive + "scores.json" if original.drive else "C:scores.json"
    if not Path(source).drive:
        await asyncio.to_thread((original / source).write_bytes, raw)
    hold = hold_preparation(monkeypatch, "never-hold")
    preparation = ModelSelectionService(environment={"ORKET_MODEL_CODER": "candidate"}).prepare(
        preferences={}, user_settings=score_settings(source))
    if Path(source).drive:
        with pytest.raises(ValueError, match="E_PROCESS_DRIVE_RELATIVE_PATH_UNSUPPORTED"):
            await preparation
        assert not hold.labels and not hold.score_calls and not hold.observations
    else:
        # A colon is a regular POSIX filename, not hidden per-drive directory state.
        prepared = await preparation
        decision = prepared.select("coder")
        assert decision.final_model == "policy-fallback" and decision.score == 10
        assert decision.score_source.path == str(original / source)
        assert len(hold.score_calls) == 1 and len(hold.observations) == 1
