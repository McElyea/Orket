"""Real authored inventory keeps admitted roots and missing-root failures visible."""
import ast
import asyncio
import json

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.driver import OrketDriver
from tests.integration.test_driver_inventory_inputs import capturing_provider
from tests.integration.test_driver_inventory_ownership import hold_inventory_read

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_driver_inventory_binds_roots_before_native_scan(test_root, tmp_path, monkeypatch):
    files = AsyncFileTools(test_root)
    for name in ("model/core/teams/chosen.json", "model/core/skills/support.json",
                 "model/core/epics/legacy.json", "config/epics/authored.json", "config/rocks/selected.json"):
        await files.write_file(name, json.dumps({"name": "inventory-only"}))
    provider, calls = capturing_provider()
    driver = await asyncio.to_thread(
        OrketDriver, project_root=test_root, provider=provider, strict_config=False, environment={})
    state = hold_inventory_read(monkeypatch, test_root, "inventory", False)
    task = asyncio.create_task(driver.process_request("settings"))
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if task.done():
                    await task
                await asyncio.sleep(.001)
        intruder = tmp_path / "intruder"
        await asyncio.to_thread(intruder.mkdir)
        driver.project_root, driver.model_root = intruder, intruder / "model"
        monkeypatch.chdir(intruder)
        monkeypatch.setenv("ORKET_MODEL_CLIENT_NODE", "retired-after-admission")
        state.release.set()
        assert await asyncio.wait_for(task, 5) == "ready"
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
    context = ast.literal_eval(calls[0][1]["content"].split("\nRequest:", 1)[0].removeprefix("Context: "))
    assert context == {
        "inventory": {"departments": {"core": {"teams": ["chosen"], "skills": ["support"]}}},
        "active_rocks": ["selected"], "active_epics": ["authored", "legacy"], "request": "settings"}
    assert state.finished.is_set() and all(stream.closed for stream in state.files)


async def test_missing_model_root_remains_failure_without_provider_dispatch(tmp_path):
    provider, calls = capturing_provider()
    driver = await asyncio.to_thread(
        OrketDriver, project_root=tmp_path, provider=provider, strict_config=False, environment={})
    with pytest.raises(FileNotFoundError):
        await driver.process_request("settings")
    assert not calls
