"""Integration: complete async runtime-input capture has one retained native owner."""
# Layer: integration
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Iterator, Mapping
from functools import partial
from pathlib import Path
from typing import Any

import aiosqlite
import pytest

import orket.application.services.runtime_construction_inputs as inputs_module
import orket.settings as settings_module
from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
HOLD_SECONDS = 0.75
RESPONSIVENESS_SECONDS = 0.5


class _HeldMapping(Mapping[str, str]):
    def __init__(self, values: dict[str, str], *, failure: ValueError | None = None) -> None:
        self._values = dict(values)
        self._failure = failure
        self.entered = threading.Event()
        self.release = threading.Event()
        self.iteration_finished = threading.Event()
        self.hook_threads: list[int] = []
        self.hook_names: list[str] = []
        self.hold_elapsed: float | None = None
        self.released_by_owner: bool | None = None

    def _observe(self, name: str) -> None:
        self.hook_threads.append(threading.get_ident())
        self.hook_names.append(name)

    def __iter__(self) -> Iterator[str]:
        self._observe("iter")
        self.entered.set()
        started = time.monotonic()
        self.released_by_owner = self.release.wait(HOLD_SECONDS)
        self.hold_elapsed = time.monotonic() - started
        self.iteration_finished.set()
        if self._failure is not None:
            raise self._failure
        return iter(tuple(self._values))

    def __len__(self) -> int:
        self._observe("len")
        return len(self._values)

    def __getitem__(self, key: str) -> str:
        self._observe("getitem")
        return self._values[key]

    def mutate(self, key: str, value: str) -> None:
        self._values[key] = value

    def observation(self) -> dict[str, Any]:
        return {
            "hook_threads": list(self.hook_threads),
            "hook_names": list(self.hook_names),
            "hold_elapsed": self.hold_elapsed,
            "released_by_owner": self.released_by_owner,
            "iteration_finished": self.iteration_finished.is_set(),
        }


def _write_settings_inputs(settings_path: Path, preferences_path: Path) -> None:
    settings_path.write_text("{}", encoding="utf-8")
    preferences_path.write_text(
        '{"models":{},"_meta":{"migration_markers":{"legacy_model_preferences_v1":true}}}',
        encoding="utf-8",
    )


def _install_native_observers(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, list[int]], Any]:
    observed = {name: [] for name in ("root", "location", "serialization", "immutable")}
    path_type = inputs_module.Path
    location = settings_module._capture_location
    json_module = inputs_module.json
    dumps = json_module.dumps
    immutable = inputs_module.MappingProxyType

    class ObservedPath:
        @staticmethod
        def cwd() -> Path:
            observed["root"].append(threading.get_ident())
            return path_type.cwd()

    def observed_location():
        observed["location"].append(threading.get_ident())
        return location()

    def observed_dumps(*args, **kwargs):
        observed["serialization"].append(threading.get_ident())
        return dumps(*args, **kwargs)

    class ObservedJson:
        loads = staticmethod(json_module.loads)
        dumps = staticmethod(observed_dumps)

    def observed_immutable(value):
        observed["immutable"].append(threading.get_ident())
        return immutable(value)

    monkeypatch.setattr(inputs_module, "Path", ObservedPath)
    monkeypatch.setattr(settings_module, "_capture_location", observed_location)
    monkeypatch.setattr(inputs_module, "json", ObservedJson)
    monkeypatch.setattr(inputs_module, "MappingProxyType", observed_immutable)
    return observed, dumps


async def _physical_sqlite(path: Path, started: float) -> dict[str, Any]:
    async with aiosqlite.connect(path) as connection:
        await connection.execute("CREATE TABLE observation (value INTEGER NOT NULL)")
        await connection.execute("INSERT INTO observation VALUES (41)")
        await connection.commit()
        cursor = await connection.execute("SELECT value FROM observation")
        row = await cursor.fetchone()
        await cursor.close()
    elapsed = asyncio.get_running_loop().time() - started
    exists = await run_owned_thread(path.is_file, label="fixture-runtime-capture-sqlite-readback")
    return {"elapsed": elapsed, "row": list(row) if row is not None else None, "physical_exists": exists}


async def _wait_entered(mapping: _HeldMapping) -> bool:
    return await run_owned_thread(
        partial(mapping.entered.wait, 2.0),
        label="fixture-runtime-capture-mapping-admission",
    )


async def _settle(task: asyncio.Task, mapping: _HeldMapping) -> tuple[str, Any]:
    mapping.release.set()
    try:
        return "returned", await task
    except asyncio.CancelledError as error:
        return "cancelled", error
    except ValueError as error:
        return "value_error", error


# Layer: integration
async def test_complete_capture_runs_hostile_mapping_and_finalization_off_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property,
) -> None:
    settings_path, preferences_path = tmp_path / "settings.json", tmp_path / "preferences.json"
    await run_owned_thread(
        partial(_write_settings_inputs, settings_path, preferences_path),
        label="fixture-runtime-capture-settings-write",
    )
    settings_module.set_settings_file(settings_path)
    settings_module.set_preferences_file(preferences_path)
    monkeypatch.chdir(tmp_path)
    environment = _HeldMapping({"CAPTURE_VALUE": "original", "EMPTY_VALUE": ""})
    native, original_dumps = _install_native_observers(monkeypatch)
    stdlib_json_unchanged = json.dumps is original_dumps
    caller_thread = threading.get_ident()
    started = asyncio.get_running_loop().time()
    capture = asyncio.create_task(RuntimeConstructionInputs.capture_async(environment=environment))
    try:
        entered = await _wait_entered(environment)
        sqlite = await _physical_sqlite(tmp_path / "responsive.sqlite3", started)
        pending_during_hold = not capture.done()
        captured = await asyncio.wait_for(capture, 3.0)
    finally:
        environment.release.set()
        await asyncio.gather(capture, return_exceptions=True)
    environment.mutate("CAPTURE_VALUE", "rotated")
    worker_threads = set(environment.hook_threads)
    for values in native.values():
        worker_threads.update(values)
    observation = {
        "entered": entered,
        "caller_thread": caller_thread,
        "worker_threads": sorted(worker_threads),
        "mapping": environment.observation(),
        "native_threads": native,
        "sqlite": sqlite,
        "pending_during_hold": pending_during_hold,
        "stdlib_json_unchanged": stdlib_json_unchanged,
        "root": str(captured.invocation_root),
        "environment": dict(captured.environment),
        "settings": captured.user_settings(),
        "preferences": captured.user_preferences(),
    }
    record_property("runtime_capture_owner_observation", original_dumps(observation, sort_keys=True))
    assert (
        entered
        and len(worker_threads) == 1
        and caller_thread not in worker_threads
        and all(values and set(values) == worker_threads for values in native.values())
        and environment.hold_elapsed is not None
        and environment.hold_elapsed >= HOLD_SECONDS
        and sqlite == {"elapsed": sqlite["elapsed"], "row": [41], "physical_exists": True}
        and sqlite["elapsed"] < RESPONSIVENESS_SECONDS
        and pending_during_hold
        and stdlib_json_unchanged
        and captured.invocation_root == tmp_path
        and dict(captured.environment) == {"CAPTURE_VALUE": "original", "EMPTY_VALUE": ""}
        and captured.user_settings() == {}
        and captured.user_preferences()["models"] == {}
    ), observation


# Layer: integration
@pytest.mark.parametrize("cancel_requests", [1, 3])
async def test_capture_cancellation_waits_for_hostile_mapping_settlement(
    cancel_requests: int,
    record_property,
) -> None:
    settings_module.set_runtime_settings_context(user_settings={}, user_preferences={})
    environment = _HeldMapping({"CANCEL_VALUE": "captured"})
    caller_thread = threading.get_ident()
    capture = asyncio.create_task(RuntimeConstructionInputs.capture_async(environment=environment))
    try:
        entered = await _wait_entered(environment)
        pending_after_cancel = []
        for _ in range(cancel_requests):
            capture.cancel()
            await asyncio.sleep(0)
            pending_after_cancel.append(not capture.done())
        outcome, _value = await _settle(capture, environment)
    finally:
        environment.release.set()
        await asyncio.gather(capture, return_exceptions=True)
    observation = {
        "cancel_requests": cancel_requests,
        "entered": entered,
        "pending_after_cancel": pending_after_cancel,
        "outcome": outcome,
        "outward_type": type(_value).__name__,
        "caller_thread": caller_thread,
        "mapping": environment.observation(),
    }
    record_property("runtime_capture_cancellation_observation", json.dumps(observation, sort_keys=True))
    assert (
        entered
        and all(pending_after_cancel)
        and outcome == "cancelled"
        and environment.iteration_finished.is_set()
        and environment.hook_threads
        and len(set(environment.hook_threads)) == 1
        and caller_thread not in environment.hook_threads
    ), observation


# Layer: integration
async def test_capture_native_failure_precedes_cancellation(
    record_property,
) -> None:
    settings_module.set_runtime_settings_context(user_settings={}, user_preferences={})
    failure = ValueError("E_RUNTIME_CAPTURE_NATIVE_FAILURE")
    environment = _HeldMapping({"FAILURE_VALUE": "captured"}, failure=failure)
    caller_thread = threading.get_ident()
    capture = asyncio.create_task(RuntimeConstructionInputs.capture_async(environment=environment))
    try:
        entered = await _wait_entered(environment)
        capture.cancel()
        await asyncio.sleep(0)
        pending_after_cancel = not capture.done()
        outcome, outward = await _settle(capture, environment)
    finally:
        environment.release.set()
        await asyncio.gather(capture, return_exceptions=True)
    observation = {
        "entered": entered,
        "pending_after_cancel": pending_after_cancel,
        "outcome": outcome,
        "outward_is_native_failure": outward is failure,
        "outward_type": type(outward).__name__,
        "outward_message": str(outward),
        "caller_thread": caller_thread,
        "mapping": environment.observation(),
    }
    record_property("runtime_capture_failure_observation", json.dumps(observation, sort_keys=True))
    assert (
        entered
        and pending_after_cancel
        and outcome == "value_error"
        and outward is failure
        and environment.iteration_finished.is_set()
        and environment.hook_threads
        and len(set(environment.hook_threads)) == 1
        and caller_thread not in environment.hook_threads
    ), observation
