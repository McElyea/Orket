"""Public operator commands against actual model trees and native mutation guards."""
import asyncio
import json

import pytest

from orket.application.services.driver_command_service import DriverCommandService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _service(root):
    return DriverCommandService(root / "model", None, ())


async def _write(path, payload):
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_text, json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("command,expected", [
    ("/list", "Usage: /list <resource> [department]"),
    ("/list cards", "Usage: /list cards <epic> [department]"),
    ("/list unknown", "Unknown list resource 'unknown'. Use /help."),
    ("/list teams absent", "No 'teams' directory found in department 'absent'."),
    ("/show", "Usage: /show <team|environment|epic|rock> <name> [department]"),
    ("/show epic absent", "epic 'absent' not found."),
    ("/create", "Usage: /create <team|environment|epic|rock> <name> [department]"),
    ("/create unknown fixture", "Unknown create resource 'unknown'. Use /help."),
    ("/create role fixture", "Create for 'role' is not supported."),
    ("/list-cards", "Usage: /list-cards <epic> [department]"),
    ("/list-cards absent", "Epic 'absent' not found in core."),
    ("/add-card", "Usage: /add-card <epic> <seat> <priority> <summary...> [--department <department>]"),
    ("/add-card fixture coder --department core", "Usage: /add-card <epic> <seat> <priority> <summary...> [--department <department>]"),
    ("/add-card fixture coder invalid summary", "Invalid priority 'invalid'. Use a numeric value."),
    ('/add-card fixture coder 1 ""', "Card summary is required."),
    ("/add-card fixture coder 1 summary", "Epic 'fixture' not found in core."),
])
async def test_usage_and_refusal_do_not_create_authored_assets(tmp_path, command, expected):
    assert await _service(tmp_path).execute(command) == expected
    assert await asyncio.to_thread(lambda: list((tmp_path / "model").rglob("*.json"))) == []


@pytest.mark.parametrize("resource,folder", [("environments", "environments"), ("rocks", "rocks")])
async def test_creation_and_duplicate_refusal_preserve_published_bytes(tmp_path, resource, folder):
    service = _service(tmp_path)
    response = await service.execute(f'/create {resource} "Fresh Asset" research')
    path = tmp_path / "model/research" / folder / "fresh_asset.json"
    assert response == f"Created {resource.rstrip('s')} 'fresh_asset' at {path.as_posix()}."
    before = await asyncio.to_thread(path.read_bytes)
    payload = json.loads(before)
    assert payload["name"] == "fresh_asset"
    assert await service.execute(f'/create {resource} "Fresh Asset" research') == (
        f"{resource} 'fresh_asset' already exists in research.")
    assert await asyncio.to_thread(path.read_bytes) == before
    assert json.loads(await service.execute(f"/show {resource} fresh_asset")) == payload
    assert await service.execute("/list departments") == "Departments (1): research"


async def test_lookup_searches_departments_and_unknown_resource_stays_missing(tmp_path):
    await asyncio.to_thread((tmp_path / "model/alpha").mkdir, parents=True)
    path = tmp_path / "model/zeta/epics/selected.json"
    await _write(path, {"name": "selected", "issues": []})
    service = _service(tmp_path)
    assert json.loads(await service.execute("/show epic selected")) == {"name": "selected", "issues": []}
    assert await service.execute("/show unknown selected") == "unknown 'selected' not found."
    assert await service.execute("/list epic zeta") == "Epic in zeta (1): selected"
    assert await service.execute("/list cards selected zeta") == "Epic 'selected' has no cards."


@pytest.mark.parametrize("payload,expected", [
    ({"name": "selected"}, "Epic 'selected' has no issues."),
    ({"issues": []}, "Epic 'selected' has no cards."),
    ({"cards": []}, "Epic 'selected' still uses the legacy child key 'cards'. Migrate it to 'issues' before using list/add card operations."),
])
async def test_card_listing_distinguishes_missing_empty_and_legacy_storage(tmp_path, payload, expected):
    path = tmp_path / "model/core/epics/selected.json"
    await _write(path, payload)
    before = await asyncio.to_thread(path.read_bytes)
    assert await _service(tmp_path).execute("/list cards selected") == expected
    assert await asyncio.to_thread(path.read_bytes) == before


async def test_add_card_normalizes_existing_legacy_children_and_retains_metadata(tmp_path):
    path = tmp_path / "model/research/epics/selected.json"
    await _write(path, {"name": "selected", "cards": [{"name": "prior"}], "description": "retained"})
    service = _service(tmp_path)
    response = await service.execute("/add_card selected coder 2 next task --department research")
    assert response == ("Added card to epic 'selected' in research: [coder] p=2.0 next task"
                        " Legacy epic child key was normalized to 'issues'.")
    payload = json.loads(await asyncio.to_thread(path.read_bytes))
    assert payload == {"name": "selected", "description": "retained", "issues": [
        {"name": "prior"}, {"summary": "next task", "seat": "coder", "priority": 2.0}]}
    assert await service.execute("/list_cards selected research") == (
        "Cards in selected (2):\n1. [unspecified] p=n/a prior\n2. [coder] p=2.0 next task")
