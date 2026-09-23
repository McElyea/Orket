"""Native pipeline construction does not admit unused preference migration.

This covers direct ``ExecutionPipeline`` construction, whose consumed inputs are
root, environment, and user settings. Full Engine/CLI bootstrap still owns user
preference admission and is intentionally outside this narrow contract.
"""
from __future__ import annotations

import asyncio
import threading
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest

from orket import settings
from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.settings_file_store import hold_settings_files
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_result_lifetime import open_runtime_owner
from orket.core.contracts.local_file_lock import LocalFileLockError
from orket.runtime.execution.execution_pipeline import ExecutionPipeline

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
SETTINGS_BYTES = b'{\n  "keep": "settings",\n  "value": 7\n}\n'
PREFERENCES_BYTES = (
    b'{\n  "models": {"coder": "retained"},\n'
    b'  "_meta": {"migration_markers": {"legacy_model_preferences_v1": true}}\n}\n'
)


async def _configure_physical_inputs(root: Path) -> tuple[Path, Path]:
    selected = root / "selected-settings"
    settings_path = selected / "user_settings.json"
    preferences_path = selected / "preferences.json"
    await asyncio.to_thread(selected.mkdir, parents=True)
    await asyncio.gather(
        asyncio.to_thread(settings_path.write_bytes, SETTINGS_BYTES),
        asyncio.to_thread(preferences_path.write_bytes, PREFERENCES_BYTES),
    )
    settings.set_settings_file(settings_path)
    settings.set_preferences_file(preferences_path)
    settings.clear_runtime_settings_context()
    return settings_path, preferences_path


def _hold_selected_settings(paths: tuple[Path, Path], state: SimpleNamespace) -> None:
    try:
        with hold_settings_files(paths):
            state.entered.set()
            if not state.release.wait(10):
                raise TimeoutError("settings-lock release deadline")
    finally:
        state.finished.set()


async def _observe_real_sqlite(database: Path) -> None:
    async with asyncio.timeout(0.5):
        async with aiosqlite.connect(database) as connection:
            await connection.execute("CREATE TABLE preference_probe (value INTEGER NOT NULL)")
            await connection.execute("INSERT INTO preference_probe VALUES (42)")
            await connection.commit()
            assert await (await connection.execute("SELECT value FROM preference_probe")).fetchone() == (42,)


async def _open_native_pipeline(test_root: Path, workspace: Path, database: Path) -> None:
    construct = partial(
        ExecutionPipeline,
        workspace,
        department="core",
        db_path=str(database),
        config_root=test_root,
    )
    async with open_runtime_owner(construct, label="native-pipeline-preference-admission") as pipeline:
        captured = pipeline.runtime_context.construction_inputs
        assert captured is pipeline.pipeline_wiring_service.construction_inputs
        assert captured.user_preferences_json is None
        await pipeline.initialize()
        await _observe_real_sqlite(database)


@pytest.mark.parametrize("lock_preferences", [False, True], ids=["healthy-unheld", "preference-lock-held"])
async def test_native_pipeline_does_not_admit_unused_preference_migration(
    test_root, workspace, db_path, lock_preferences,
):
    settings_path, preferences_path = await _configure_physical_inputs(test_root)
    original = (SETTINGS_BYTES, PREFERENCES_BYTES)
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event())
    lock_task = None
    try:
        if lock_preferences:
            lock_task = asyncio.create_task(run_owned_thread(
                lambda: _hold_selected_settings((settings_path, preferences_path), state),
                label="held-preference-migration-owner",
            ))
            assert await asyncio.to_thread(state.entered.wait, 5)
        pipeline_task = asyncio.create_task(_open_native_pipeline(test_root, workspace, Path(db_path)))
        outcome = (await asyncio.gather(pipeline_task, return_exceptions=True))[0]
    finally:
        state.release.set()
        lock_outcome = None if lock_task is None else (await asyncio.gather(lock_task, return_exceptions=True))[0]

    observed = await asyncio.gather(
        asyncio.to_thread(settings_path.read_bytes),
        asyncio.to_thread(preferences_path.read_bytes),
    )
    assert tuple(observed) == original
    if isinstance(lock_outcome, BaseException):
        raise lock_outcome
    assert not lock_preferences or state.finished.is_set()
    if isinstance(outcome, BaseException):
        raise outcome
    database = Path(db_path)
    assert await asyncio.to_thread(database.is_file)
    assert (await asyncio.to_thread(database.stat)).st_size > 0


@pytest.mark.parametrize("lock_preferences", [False, True], ids=["full-unheld", "full-lock-held"])
async def test_full_construction_capture_retains_preference_admission(test_root, lock_preferences):
    settings_path, preferences_path = await _configure_physical_inputs(test_root)
    original = (SETTINGS_BYTES, PREFERENCES_BYTES)
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event())
    lock_task = None
    try:
        if lock_preferences:
            lock_task = asyncio.create_task(run_owned_thread(
                lambda: _hold_selected_settings((settings_path, preferences_path), state),
                label="held-full-preference-owner",
            ))
            assert await asyncio.to_thread(state.entered.wait, 5)
        capture_task = asyncio.create_task(run_owned_thread(
            RuntimeConstructionInputs.capture,
            label="full-runtime-construction-capture",
        ))
        outcome = (await asyncio.gather(capture_task, return_exceptions=True))[0]
    finally:
        state.release.set()
        lock_outcome = None if lock_task is None else (await asyncio.gather(lock_task, return_exceptions=True))[0]

    observed = await asyncio.gather(
        asyncio.to_thread(settings_path.read_bytes),
        asyncio.to_thread(preferences_path.read_bytes),
    )
    assert tuple(observed) == original
    if isinstance(lock_outcome, BaseException):
        raise lock_outcome
    assert not lock_preferences or state.finished.is_set()
    if lock_preferences:
        assert isinstance(outcome, LocalFileLockError) and "E_SETTINGS_UNCERTAIN:owner_busy" in str(outcome)
    else:
        if isinstance(outcome, BaseException):
            raise outcome
        assert outcome.user_settings() == {"keep": "settings", "value": 7}
        assert outcome.user_preferences()["models"] == {"coder": "retained"}
