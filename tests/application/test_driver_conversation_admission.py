"""Public driver contracts with a controlled provider; no actual inference claim."""
import asyncio
from types import SimpleNamespace

import pytest
import pytest_asyncio

from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.driver import OrketDriver

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


class FixtureProvider:
    model = "fixture"

    def __init__(self):
        self.content = "controlled conversation"
        self.calls = []
        self.closed = False

    async def complete(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)

    async def close(self):
        self.closed = True


@pytest_asyncio.fixture
async def conversation_driver(tmp_path):
    await asyncio.to_thread((tmp_path / "model/core").mkdir, parents=True)
    provider = FixtureProvider()
    driver = await OrketDriver.create(project_root=tmp_path, provider=provider, strict_config=False,
        construction_inputs=RuntimeConstructionInputs(tmp_path, {}, "{}", "{}"))
    try:
        yield driver, provider
    finally:
        await driver.close()
    assert provider.closed
    assert await asyncio.to_thread(lambda: list((tmp_path / "model").rglob("*.json"))) == []
    assert not await asyncio.to_thread((tmp_path / "config").exists)


@pytest.mark.parametrize("message,expected", [
    ("", "I am here."), ("what?", "I can explain capabilities"),
    ("didn't think so", "Fair pushback."),
    ("calculate (9 - 3) * 2 / 4", "3"), ("compute -3 + +2", "-1"),
    ("what's 1 / 2?", "0.5"),
])
async def test_deterministic_replies_preserve_model_silence(conversation_driver, message, expected):
    driver, provider = conversation_driver
    response = await driver.process_request(message)
    assert response == expected if expected in {"3", "-1", "0.5"} else response.startswith(expected)
    assert provider.calls == []


@pytest.mark.parametrize("message", ["calculate ?", "compute 1..2", "compute 1 / 0", "compute 2 ** 8", "compute 2(3)"])
async def test_unsupported_or_invalid_arithmetic_uses_conversation_contract(conversation_driver, message):
    driver, provider = conversation_driver
    assert await driver.process_request(message) == "controlled conversation"
    messages, = provider.calls
    assert messages[1] == {"role": "user", "content": message}
    assert "Do not produce JSON, plans, or structural board mutations" in messages[0]["content"]


@pytest.mark.parametrize("content,expected", [
    ('{"response":" answer ","reasoning":"other"}', "answer"),
    ('{"response":"","reasoning":" reason "}', "reason"),
    ('{"action":"create_epic"}', '{"action":"create_epic"}'),
    ("{invalid}", "{invalid}"),
    ("   ", "I can chat normally and help with Orket operations when you ask explicitly."),
])
async def test_conversation_model_text_cannot_become_a_board_action(conversation_driver, content, expected):
    driver, provider = conversation_driver
    provider.content = content
    assert await driver.process_request("Discuss the design tradeoffs") == expected
    assert len(provider.calls) == 1


async def test_unavailable_conversation_callable_retains_explicit_fallback(conversation_driver):
    driver, provider = conversation_driver
    provider.complete = None
    assert await driver.process_request("Discuss design tradeoffs") == (
        "I can chat normally and help with Orket operations when you ask explicitly.")
    assert provider.calls == []


@pytest.mark.parametrize("mode,content,message", [
    ("strict", "[]", "Strict JSON mode requires a JSON object envelope."),
    ("strict", "null", "Strict JSON mode requires a JSON object envelope."),
    ("strict", "{invalid}", "Strict JSON mode requires pure JSON envelope output."),
    ("compatibility", "No envelope", "Compatibility mode could not find JSON envelope"),
    ("compatibility", "{invalid}", "Expecting property name enclosed in double quotes"),
])
async def test_public_structural_route_reports_parse_refusal(conversation_driver, mode, content, message):
    driver, provider = conversation_driver
    driver.json_parse_mode, provider.content = mode, content
    response = await driver.process_request("settings")
    assert response.startswith("Driver failed to parse JSON:") and message in response
    assert len(provider.calls) == 1


async def test_public_help_exposes_actual_degraded_configuration(conversation_driver):
    driver, provider = conversation_driver
    response = await driver.process_request("/help")
    assert driver.config_degraded and len(driver.config_load_failures) == 2
    assert "Config load status: degraded (2 dependency load failure(s))." in response
    assert "Active prompting mode: fallback" in response
    assert "Active JSON parse mode: compatibility" in response
    assert provider.calls == []
