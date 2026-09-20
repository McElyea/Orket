# Layer: integration. Controlled driver provider; actual command interpretation and resource boundary.
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.driver import OrketDriver


def _driver(root: Path) -> OrketDriver:
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = root / "model"
    driver.workspace_root = root / "workspace"
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)
    return driver


@pytest.mark.asyncio
async def test_operator_canary_conversation_flow(tmp_path):
    driver = _driver(tmp_path)

    hello = await driver.process_request("hello")
    assert "chat normally" in hello.lower()

    app = await driver.process_request("can you tell me about this application?")
    assert "orket" in app.lower()

    converse = await driver.process_request("can you really converse?")
    assert converse.lower().startswith("yes")


@pytest.mark.asyncio
async def test_operator_canary_capability_flow(tmp_path):
    driver = _driver(tmp_path)
    response = await driver.process_request("What can you do in this environment?")

    assert "Operator CLI is available." in response
    assert "/capabilities" in response
    assert "Conversation mode is on by default" in response
