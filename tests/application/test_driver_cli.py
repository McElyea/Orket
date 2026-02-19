import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.driver import OrketDriver


def _build_driver(tmp_path: Path) -> OrketDriver:
    model_root = tmp_path / "model"
    core = model_root / "core"
    for folder in ("teams", "environments", "epics", "rocks", "roles", "dialects", "skills"):
        (core / folder).mkdir(parents=True, exist_ok=True)

    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = model_root
    driver.fs = AsyncFileTools(tmp_path)
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)
    return driver


@pytest.mark.asyncio
async def test_cli_list_departments(tmp_path: Path):
    driver = _build_driver(tmp_path)
    response = await driver.process_request("/list departments")
    assert "Departments" in response
    assert "core" in response


@pytest.mark.asyncio
async def test_cli_create_and_show_team(tmp_path: Path):
    driver = _build_driver(tmp_path)
    create = await driver.process_request("/create team platform_ops core")
    assert "Created team 'platform_ops'" in create

    show = await driver.process_request("/show team platform_ops core")
    payload = json.loads(show)
    assert payload["name"] == "platform_ops"
    assert "code_reviewer" in payload["roles"]


@pytest.mark.asyncio
async def test_cli_create_environment_and_list(tmp_path: Path):
    driver = _build_driver(tmp_path)
    create = await driver.process_request("/create environment staging core")
    assert "Created environment 'staging'" in create

    listed = await driver.process_request("/list environments core")
    assert "staging" in listed


@pytest.mark.asyncio
async def test_cli_add_card_and_list_cards(tmp_path: Path):
    driver = _build_driver(tmp_path)
    await driver.process_request("/create epic payments_upgrade core")

    added = await driver.process_request('/add-card payments_upgrade coder 2.5 "Implement retry policy" --department core')
    assert "Added card to epic 'payments_upgrade'" in added

    listed = await driver.process_request("/list-cards payments_upgrade core")
    assert "Implement retry policy" in listed
    assert "[coder]" in listed

