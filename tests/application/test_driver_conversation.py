from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest

from orket.driver import OrketDriver


@pytest.mark.asyncio
async def test_process_request_conversation_short_circuits_model_call():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None

    class _Provider:
        def __init__(self):
            self.called = False

        async def complete(self, _messages):
            self.called = True
            return SimpleNamespace(content='{"action":"create_epic"}')

    provider = _Provider()
    driver.provider = provider

    async def _fake_inventory(_self):
        return {"departments": {}}

    driver._get_inventory = MethodType(_fake_inventory, driver)

    response = await driver.process_request("hi")

    assert provider.called is False
    assert "chat normally" in response.lower()


@pytest.mark.asyncio
async def test_execute_plan_converse_response():
    driver = OrketDriver.__new__(OrketDriver)
    result = await driver.execute_plan(
        {"action": "converse", "response": "I can chat with you.", "reasoning": "conversation"}
    )
    assert result == "I can chat with you."


@pytest.mark.asyncio
async def test_execute_plan_unknown_action_does_not_emit_structural_fallback():
    driver = OrketDriver.__new__(OrketDriver)
    result = await driver.execute_plan({"action": "unknown_action", "reasoning": "none"})
    assert "No structural action taken." not in result
    assert "Strategic Insight:" not in result


def test_should_handle_as_conversation_detects_structural_intent():
    driver = OrketDriver.__new__(OrketDriver)
    assert driver._should_handle_as_conversation("create epic for billing rewrite") is False
    assert driver._should_handle_as_conversation("you are not set up to converse anymore") is True
    assert driver._has_explicit_structural_intent("/create epic billing_rewrite core") is True


@pytest.mark.asyncio
async def test_process_request_answers_basic_math_without_structural_action():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("What is 2 + 2?")

    assert response == "4"


@pytest.mark.asyncio
async def test_process_request_handles_cool_as_conversation():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("Cool")

    assert "nice" in response.lower()


@pytest.mark.asyncio
async def test_process_request_capabilities_question_returns_help():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("What can you do in this environment?")

    assert "Operator CLI is available." in response
    assert "/list" in response
    assert "Conversation mode is on by default" in response


@pytest.mark.asyncio
async def test_process_request_anything_else_not_generic_fallback():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("Do you say anything else?")

    assert "Understood. What would you like to talk about?" not in response
    assert "/help" in response


@pytest.mark.asyncio
async def test_process_request_about_application_question():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("can you tell me about this application?")

    assert "Orket" in response
    assert "/list" in response


@pytest.mark.asyncio
async def test_process_request_can_you_converse_question():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("can you converse at all?")

    assert response.lower().startswith("yes")
    assert "converse" in response.lower()


@pytest.mark.asyncio
async def test_process_request_can_you_really_converse_question():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("Can you really converse?")

    assert response.lower().startswith("yes")
    assert "converse" in response.lower()


@pytest.mark.asyncio
async def test_process_request_plain_text_with_apostrophe_not_cli_error():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("I didn't think so.")

    assert "Invalid command syntax" not in response
    assert "pushback" in response.lower()


@pytest.mark.asyncio
async def test_process_request_what_question_not_generic_fallback():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)

    response = await driver.process_request("What?")

    assert "Understood. What would you like to talk about?" not in response
    assert "capabilities" in response.lower()


@pytest.mark.asyncio
async def test_process_request_blocks_implicit_structural_action_from_model():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None

    class _Provider:
        async def complete(self, _messages):
            return SimpleNamespace(
                content='{"action":"create_epic","new_asset":{"name":"silent_change"},"reasoning":"do it"}'
            )

    driver.provider = _Provider()

    response = await driver.process_request("settings")

    assert "please ask explicitly for a board change" in response.lower()
