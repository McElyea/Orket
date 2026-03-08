from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest

from orket.driver import OrketDriver
from orket.exceptions import ModelConnectionError


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


@pytest.mark.asyncio
async def test_execute_plan_assign_team_missing_fields_uses_fallback_labels(monkeypatch):
    """Layer: unit. Verifies assign_team payload parsing fallback labels."""
    driver = OrketDriver.__new__(OrketDriver)
    events = []

    def _capture(event_name, payload, _workspace, role=None):
        events.append((event_name, payload, role))

    monkeypatch.setattr("orket.driver.log_event", _capture)
    result = await driver.execute_plan({"action": "assign_team", "reasoning": "test suggestion"})

    assert "unknown_team" in result
    assert "unknown_department" in result
    assert result.startswith("Resource Selection Suggestion:")
    assert events[0][0] == "team_assignment_suggested"
    assert events[0][1]["mode"] == "suggestion_only"


@pytest.mark.asyncio
async def test_execute_plan_assign_team_contract_is_suggestion_only(monkeypatch):
    """Layer: contract. Verifies assign_team response and telemetry semantics."""
    driver = OrketDriver.__new__(OrketDriver)
    events = []

    def _capture(event_name, payload, _workspace, role=None):
        events.append((event_name, payload, role))

    monkeypatch.setattr("orket.driver.log_event", _capture)
    result = await driver.execute_plan(
        {
            "action": "assign_team",
            "suggested_team": "runtime",
            "suggested_department": "core",
            "reasoning": "best fit for current incident",
        }
    )

    assert "Resource Selection Suggestion:" in result
    assert "No runtime team switch was applied." in result
    assert "Switching to Team" not in result
    assert events[0][0] == "team_assignment_suggested"
    assert events[0][1]["team"] == "runtime"
    assert events[0][1]["department"] == "core"
    assert events[0][1]["mode"] == "suggestion_only"


def test_should_route_to_conversation_detects_structural_intent():
    """Layer: unit. Verifies the conversation route is only the fallback when no explicit structural intent is present."""
    driver = OrketDriver.__new__(OrketDriver)
    assert driver._should_route_to_conversation("create epic for billing rewrite") is False
    assert driver._should_route_to_conversation("you are not set up to converse anymore") is True
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
    """Layer: integration. Verifies capabilities output states the exact supported action surface."""
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)
    driver.prompting_mode = "fallback"
    driver.json_parse_mode = "compatibility"
    driver.config_degraded = False
    driver.config_load_failures = []

    response = await driver.process_request("What can you do in this environment?")

    assert "Operator CLI is available." in response
    assert "/list" in response
    assert "Supported model-directed actions:" in response
    assert "assign_team (suggestion only; no runtime team switch)" in response
    assert "structural changes: create_issue, create_epic, create_rock" in response
    assert "Active prompting mode: fallback" in response
    assert "Active JSON parse mode: compatibility" in response
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
async def test_process_request_general_conversation_uses_model_reply():
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None

    class _Provider:
        async def complete(self, _messages):
            return SimpleNamespace(content="I can help reason through that tradeoff.")

    driver.provider = _Provider()

    response = await driver.process_request("Can we discuss tradeoffs in this design?")

    assert response == "I can help reason through that tradeoff."


@pytest.mark.asyncio
async def test_conversation_model_reply_logs_provider_failures(monkeypatch):
    """Layer: contract. Verifies swallowed conversation provider errors are recorded before the fallback path is used."""
    driver = OrketDriver.__new__(OrketDriver)
    driver.provider = SimpleNamespace()
    driver.workspace_root = Path("workspace/default")
    events = []

    async def _boom(_messages):
        raise ModelConnectionError("provider offline")

    def _capture(event_name, payload, _workspace, role=None):
        events.append((event_name, payload, role))

    driver.provider.complete = _boom
    monkeypatch.setattr("orket.driver_support_conversation.log_event", _capture)

    response = await driver._conversation_model_reply("Can we discuss tradeoffs in this design?")

    assert response is None
    assert events == [
        (
            "conversation_model_error",
            {"error": "provider offline", "error_type": "ModelConnectionError"},
            "DRIVER",
        )
    ]


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


@pytest.mark.asyncio
async def test_process_request_assign_team_reports_suggestion_only():
    """Layer: integration. Verifies model->execute_plan path keeps assign_team non-mutating."""
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None

    class _Provider:
        async def complete(self, _messages):
            return SimpleNamespace(
                content=(
                    '{"action":"assign_team","suggested_team":"runtime","suggested_department":"core",'
                    '"reasoning":"best fit"}'
                )
            )

    driver.provider = _Provider()

    response = await driver.process_request("assign team for incident triage")

    assert response.startswith("Resource Selection Suggestion:")
    assert "No runtime team switch was applied." in response


@pytest.mark.asyncio
async def test_process_request_reforge_bare_and_slash_forms_match_usage_contract():
    """Layer: integration. Verifies CLI recognizer supports bare and slash reforge forms."""
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)
    driver.reforger_tools = SimpleNamespace()

    bare = await driver.process_request("reforge")
    slash = await driver.process_request("/reforge")

    assert bare == "Usage: /reforge <inspect|run> [options]"
    assert slash == "Usage: /reforge <inspect|run> [options]"


@pytest.mark.asyncio
async def test_process_request_capabilities_reports_degraded_config_status():
    """Layer: integration. Verifies operator-visible degradation status in capabilities output."""
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)
    driver.prompting_mode = "fallback"
    driver.config_degraded = True
    driver.config_load_failures = [{"dependency": "skill.operations_lead"}]

    response = await driver.process_request("what can you do in this environment?")

    assert "Active prompting mode: fallback" in response
    assert "Config load status: degraded (1 dependency load failure(s))." in response


@pytest.mark.asyncio
async def test_execute_plan_structural_error_omits_strategic_insight():
    """Layer: unit. Verifies structural failure text is returned plainly without success-flavored strategic narration."""
    driver = OrketDriver.__new__(OrketDriver)

    async def _fake_structural_change(_self, _plan):
        return "Error: epic not found"

    driver._execute_structural_change = MethodType(_fake_structural_change, driver)

    result = await driver.execute_plan({"action": "create_epic", "reasoning": "build a new roadmap lane"})

    assert result == "Error: epic not found"
