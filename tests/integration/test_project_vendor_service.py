"""Integration proof for project catalog and actual runtime card observations."""
import asyncio
import json
import threading

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.local_project_vendor import LocalProjectVendor
from orket.application.services.project_vendor_catalog import ProjectCatalogLocation
from orket.application.services.project_vendor_factory import create_project_vendor
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.exceptions import CardNotFound
from orket.runtime.config.config_loader import ConfigLoader
from orket.schema import CardStatus

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _vendor(root, database):
    return LocalProjectVendor(ProjectCatalogLocation(root), database)


async def _write(path, payload):
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_text, json.dumps(payload), encoding="utf-8")


async def test_missing_card_does_not_return_a_fabricated_record(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    vendor = _vendor(tmp_path, tmp_path / "durable/db/orket_persistence.db")
    with pytest.raises(ValueError, match="Card not found"):
        await vendor.get_card_details("absent-card")


async def test_catalog_uses_selected_project_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rock_dir = tmp_path / "model/core/rocks"
    await _write(rock_dir / "selected.json", {"id": "R1", "name": "Selected", "epics": []})
    vendor = _vendor(tmp_path, tmp_path / "cards.db")
    rocks = await vendor.get_rocks()
    assert [(rock.id, rock.name) for rock in rocks] == [("selected", "Selected")]


async def test_runtime_database_does_not_follow_later_working_directory(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    await asyncio.to_thread(first.mkdir)
    await asyncio.to_thread(second.mkdir)
    monkeypatch.chdir(first)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", "durable")
    database = first / "durable/db/orket_persistence.db"
    await asyncio.to_thread(database.parent.mkdir, parents=True)
    repo = AsyncCardRepository(database)
    await repo.save({"id": "C1", "seat": "coder", "summary": "Captured database"})
    vendor = _vendor(first, database)
    monkeypatch.chdir(second)
    card = await vendor.get_card_details("C1")
    assert card.summary == "Captured database"
    assert not await asyncio.to_thread((second / "durable").exists)


@pytest.mark.parametrize("alias", ["issues", "stories", "cards"])
async def test_catalog_projects_declared_card_metadata_without_minting_ids(tmp_path, monkeypatch, alias):
    await _write(tmp_path / "model/core/epics/work.json", {alias: [
        {"id": "C1", "summary": "Declared", "note": "Details", "status": "blocked", "priority": "High", "assignee": "human"},
    ]})

    def forbidden_identity():
        raise AssertionError("A catalog read must not mint identity")

    monkeypatch.setattr("orket.schema.uuid.uuid4", forbidden_identity)
    vendor = _vendor(tmp_path, tmp_path / "cards.db")
    observed = await vendor.get_cards("work")
    assert [card.model_dump() for card in observed] == [{
        "id": "C1", "epic_id": "work", "summary": "Declared", "description": "Details",
        "status": "blocked", "assignee": "human", "priority": "3.0",
    }]


@pytest.mark.parametrize("rows,code", [
    ([{"summary": "Missing identity"}], "E_VENDOR_CARD_ID_REQUIRED"),
    ([{"id": "C1"}, {"id": "C1"}], "E_VENDOR_CARD_ID_DUPLICATE"),
    (None, "E_VENDOR_EPIC_CARDS_INVALID"),
    (["invalid"], "E_VENDOR_EPIC_CARDS_INVALID"),
])
async def test_catalog_refuses_invalid_card_observations(tmp_path, rows, code):
    await _write(tmp_path / "model/core/epics/work.json", {"issues": rows})
    with pytest.raises(ValueError, match=code):
        await _vendor(tmp_path, tmp_path / "cards.db").get_cards("work")


async def test_cross_department_epic_reference_selects_its_declared_files(tmp_path):
    await _write(tmp_path / "model/core/rocks/work.json", {
        "name": "Work", "status": "active", "epics": [{"epic": "same-name", "department": "other"}],
    })
    await _write(tmp_path / "model/core/epics/same-name.json", {"name": "Wrong department"})
    await _write(tmp_path / "model/other/epics/same-name.json", {
        "name": "Other department", "issues": [{"id": "OTHER-1", "name": "Other card"}],
    })
    vendor = _vendor(tmp_path, tmp_path / "cards.db")
    assert (await vendor.get_rocks())[0].status == "active"
    epics = await vendor.get_epics("work")
    assert [(row.id, row.name) for row in epics] == [("other/same-name", "Other department")]
    assert (await vendor.get_cards(epics[0].id))[0].id == "OTHER-1"


async def test_missing_linked_epic_is_reported(tmp_path):
    await _write(tmp_path / "model/core/rocks/work.json", {"epics": [{"epic": "absent"}]})
    with pytest.raises(CardNotFound):
        await _vendor(tmp_path, tmp_path / "cards.db").get_epics("work")


@pytest.mark.parametrize("identifier", ["../outside", "/absolute", "core/../../outside", "C:\\outside"])
async def test_catalog_refuses_reference_escape(tmp_path, identifier):
    with pytest.raises(ValueError, match="E_VENDOR_CATALOG_COMPONENT_INVALID"):
        await _vendor(tmp_path, tmp_path / "cards.db").get_cards(identifier)


async def test_status_success_follows_database_observation(tmp_path):
    database = tmp_path / "cards.db"
    repo = AsyncCardRepository(database)
    await repo.save({"id": "C1", "seat": "coder", "summary": "Real card"})
    vendor = _vendor(tmp_path, database)
    assert await vendor.update_card_status("C1", "in_progress") is True
    assert (await repo.get_by_id("C1")).status == CardStatus.IN_PROGRESS
    assert (await vendor.get_card_details("C1")).summary == "Real card"
    with pytest.raises(ValueError, match="Card not found"):
        await vendor.update_card_status("absent", "in_progress")


async def test_factory_captures_selected_department(tmp_path):
    await _write(tmp_path / "model/selected/rocks/work.json", {"name": "Selected"})
    await _write(tmp_path / "model/changed/rocks/work.json", {"name": "Changed"})
    settings = {"active_department": "selected"}
    vendor = await create_project_vendor(settings=settings, project_root=tmp_path, runtime_db=tmp_path / "cards.db")
    settings["active_department"] = "changed"
    assert (await vendor.get_rocks())[0].name == "Selected"


@pytest.mark.parametrize("status", ["done", "guard_approved"])
async def test_vendor_does_not_bypass_card_completion_admission(tmp_path, status):
    vendor = _vendor(tmp_path, tmp_path / "cards.db")
    await vendor._cards.save({"id": "C1", "seat": "coder", "summary": "Unverified"})
    with pytest.raises(CardCompletionRejected, match="E_CARD_COMPLETION_"):
        await vendor.update_card_status("C1", status)
    assert (await vendor.get_card_details("C1")).status == "ready"


async def test_status_readback_mismatch_cannot_report_success(tmp_path, monkeypatch):
    vendor = _vendor(tmp_path, tmp_path / "cards.db")
    await vendor._cards.save({"id": "C1", "seat": "coder", "summary": "Real card"})
    original = vendor._cards.update_status

    async def intervening_update(card_id, status):
        await original(card_id, status)
        await original(card_id, CardStatus.BLOCKED)

    monkeypatch.setattr(vendor._cards, "update_status", intervening_update)
    with pytest.raises(ValueError, match="E_VENDOR_CARD_STATUS_UNVERIFIED"):
        await vendor.update_card_status("C1", "in_progress")
    assert (await vendor.get_card_details("C1")).status == "blocked"


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_status_worker_retains_write_and_verification_through_interruption(tmp_path, monkeypatch, stop):
    vendor = _vendor(tmp_path, tmp_path / "cards.db")
    await vendor._cards.save({"id": "C1", "seat": "coder", "summary": "Real card"})
    entered, release, verified = asyncio.Event(), asyncio.Event(), asyncio.Event()
    update, read = vendor._cards.update_status, vendor._cards.get_by_id

    async def held(card_id, status):
        entered.set()
        await release.wait()
        return await update(card_id, status)

    async def observed(card_id):
        result = await read(card_id)
        verified.set()
        return result

    monkeypatch.setattr(vendor._cards, "update_status", held)
    monkeypatch.setattr(vendor._cards, "get_by_id", observed)
    command = vendor.update_card_status("C1", "in_progress")
    started = asyncio.get_running_loop().time()
    request = asyncio.create_task(asyncio.wait_for(command, 0.05) if stop == "timeout" else command)
    try:
        await asyncio.wait_for(entered.wait(), 3)
        await asyncio.wait_for(asyncio.sleep(0), 0.5)
        assert asyncio.get_running_loop().time() - started < 0.5
        if stop == "cancel":
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        await asyncio.sleep(0.15)
        assert not request.done() and not verified.is_set()
        released = asyncio.get_running_loop().time()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert asyncio.get_running_loop().time() - released < 3
        assert isinstance(result, asyncio.CancelledError if stop == "cancel" else TimeoutError)
        assert verified.is_set() and (await read("C1")).status == CardStatus.IN_PROGRESS
    finally:
        release.set()
        await asyncio.gather(request, return_exceptions=True)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_catalog_worker_remains_owned_until_file_scan_finishes(tmp_path, monkeypatch, stop):
    await _write(tmp_path / "model/core/rocks/work.json", {"name": "Work"})
    entered, release = threading.Event(), threading.Event()
    original = ConfigLoader.list_assets

    def held(loader, category):
        entered.set()
        assert release.wait(10)
        return original(loader, category)

    monkeypatch.setattr(ConfigLoader, "list_assets", held)
    command = _vendor(tmp_path, tmp_path / "cards.db").get_rocks()
    started = asyncio.get_running_loop().time()
    request = asyncio.create_task(asyncio.wait_for(command, 0.05) if stop == "timeout" else command)
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        await asyncio.wait_for(asyncio.sleep(0), 0.5)
        assert asyncio.get_running_loop().time() - started < 0.5
        if stop == "cancel":
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        await asyncio.sleep(0.15)
        assert not request.done()
        released = asyncio.get_running_loop().time()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert asyncio.get_running_loop().time() - released < 3
        assert isinstance(result, asyncio.CancelledError if stop == "cancel" else TimeoutError)
    finally:
        release.set()
        await asyncio.gather(request, return_exceptions=True)
