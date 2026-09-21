"""Driver config and inventory respect explicit captured environment inputs."""
import ast
import asyncio
from types import SimpleNamespace

import pytest

from orket.driver import OrketDriver

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def capturing_provider():
    calls = []

    async def complete(messages):
        calls.append(messages)
        return SimpleNamespace(content='{"action":"converse","response":"ready","reasoning":"fixture"}')

    return SimpleNamespace(model="qwen-test", complete=complete), calls


@pytest.mark.parametrize("rotation", ["before_construction", "after_construction"])
async def test_explicit_empty_environment_ignores_ambient_retired_node(test_root, monkeypatch, rotation):
    provider, calls = capturing_provider()
    environment = {}
    if rotation == "before_construction":
        monkeypatch.setenv("ORKET_MODEL_CLIENT_NODE", "retired-ambient")
    driver = await asyncio.to_thread(
        OrketDriver, project_root=test_root, provider=provider, strict_config=False, environment=environment)
    environment["ORKET_MODEL_CLIENT_NODE"] = "retired-caller-mutation"
    monkeypatch.setenv("ORKET_MODEL_CLIENT_NODE", "retired-ambient")
    assert await driver.process_request("settings") == "ready"
    context = ast.literal_eval(calls[0][1]["content"].split("\nRequest:", 1)[0].removeprefix("Context: "))
    assert context["inventory"] == {"departments": {"core": {"teams": [], "skills": []}}}
    assert context["active_rocks"] == context["active_epics"] == []


async def test_explicit_retired_node_remains_refused(test_root):
    provider, calls = capturing_provider()
    with pytest.raises(ValueError, match="ORKET_MODEL_CLIENT_NODE is retired"):
        await asyncio.to_thread(OrketDriver, project_root=test_root, provider=provider,
                                environment={"ORKET_MODEL_CLIENT_NODE": "explicit-retired"})
    assert not calls
