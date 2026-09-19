"""Integration proof over operator commands and actual model files."""
import asyncio
import json
import threading

import pytest

from orket.adapters.storage.driver_resource_store import DriverResourceStore
from orket.application.services.driver_structural_service import DriverStructuralService
from tests.application.test_driver_cli import _build_driver

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_driver_department_cannot_escape_model_root(tmp_path):
    driver = await asyncio.to_thread(_build_driver, tmp_path)
    response = await driver.process_request("/create epic escaped ../outside")
    assert response.startswith("Error:"), response
    assert not await asyncio.to_thread((tmp_path / "outside" / "epics" / "escaped.json").exists)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_driver_write_keeps_ownership_and_refuses_competing_update(tmp_path, monkeypatch, stop):
    driver = await asyncio.to_thread(_build_driver, tmp_path)
    assert (await driver.process_request("/create epic retained")).startswith("Created")
    entered, release = threading.Event(), threading.Event()
    original = DriverResourceStore.write

    def held(store, path, payload):
        if len(payload.get("issues", [])) == 1:
            entered.set()
            assert release.wait(10)
        original(store, path, payload)

    monkeypatch.setattr(DriverResourceStore, "write", held)
    command = driver.process_request("/add-card retained coder 1 first")
    request = asyncio.create_task(asyncio.wait_for(command, 0.05) if stop == "timeout" else command)
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        # A model-proposed mutation and a CLI mutation share the actual native lock.
        other = DriverStructuralService(driver.model_root, tmp_path / "workspace")
        with pytest.raises(ValueError, match="DRIVER_RESOURCE_UNCERTAIN:owner_busy"):
            await other.execute({"action": "create_issue", "target_parent": "retained",
                                 "new_asset": {"summary": "second"}})
        if stop == "cancel":
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        await asyncio.sleep(0.15)
        assert not request.done()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert isinstance(result, asyncio.CancelledError if stop == "cancel" else TimeoutError)
        retry = await driver.process_request("/add-card retained coder 2 second")
        assert retry.startswith("Added card")
        raw = await asyncio.to_thread((driver.model_root / "core/epics/retained.json").read_bytes)
        assert [row["summary"] for row in json.loads(raw)["issues"]] == ["first", "second"]
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)


async def test_driver_does_not_claim_creation_after_file_publication_failure(tmp_path, monkeypatch):
    driver = await asyncio.to_thread(_build_driver, tmp_path)

    def fail_flush(_descriptor):
        raise OSError("fixture fsync refusal")

    monkeypatch.setattr("orket.adapters.storage.verified_file.os.fsync", fail_flush)
    response = await driver.process_request("/create epic refused")
    assert response == "Error: fixture fsync refusal"
    assert not await asyncio.to_thread((driver.model_root / "core/epics/refused.json").exists)


async def test_structural_plan_is_captured_before_worker_admission(tmp_path, monkeypatch):
    driver = await asyncio.to_thread(_build_driver, tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = DriverResourceStore.__init__

    def held(store, root):
        entered.set()
        assert release.wait(10)
        original(store, root)

    monkeypatch.setattr(DriverResourceStore, "__init__", held)
    plan = {"action": "create_rock", "new_asset": {"name": "captured", "epics": []}}
    request = asyncio.create_task(DriverStructuralService(driver.model_root, tmp_path / "workspace").execute(plan))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        plan["new_asset"]["name"] = "late"
        plan["new_asset"]["epics"].append({"epic": "late"})
        release.set()
        assert "captured" in await asyncio.wait_for(request, 3)
        raw = await asyncio.to_thread((driver.model_root / "core/rocks/captured.json").read_bytes)
        assert json.loads(raw) == {"name": "captured", "epics": []}
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
