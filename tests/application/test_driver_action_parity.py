from __future__ import annotations

from types import MethodType, SimpleNamespace
from pathlib import Path

import pytest

from orket.driver import OrketDriver


def test_fallback_prompt_advertises_only_canonical_actions():
    """Layer: contract. Verifies fallback prompt action surface is derived from canonical registry."""
    driver = OrketDriver.__new__(OrketDriver)

    prompt = driver._build_fallback_system_prompt()
    for action in driver._supported_plan_actions():
        assert action in prompt
    assert "create, update, move, delete, direct" not in prompt
    assert "constrained action router" in prompt.lower()


@pytest.mark.asyncio
async def test_execute_plan_handles_all_advertised_actions(monkeypatch):
    """Layer: contract. Verifies every advertised action executes without unsupported-action fallback."""
    driver = OrketDriver.__new__(OrketDriver)

    async def _fake_structural_change(_self, _plan):
        return "structural change applied"

    monkeypatch.setattr("orket.driver.log_event", lambda *_args, **_kwargs: None)
    driver._execute_structural_change = MethodType(_fake_structural_change, driver)

    payloads = {
        "assign_team": {"action": "assign_team", "suggested_team": "runtime", "suggested_department": "core", "reasoning": "fit"},
        "turn_directive": {"action": "turn_directive", "target_seat": "coder", "directive": "ship fix", "reasoning": "priority"},
        "converse": {"action": "converse", "response": "ok", "reasoning": "conversation"},
        "chat": {"action": "chat", "response": "ok", "reasoning": "conversation"},
        "respond": {"action": "respond", "response": "ok", "reasoning": "conversation"},
        "conversation": {"action": "conversation", "response": "ok", "reasoning": "conversation"},
        "create_issue": {"action": "create_issue", "reasoning": "structural"},
        "create_epic": {"action": "create_epic", "reasoning": "structural"},
        "create_rock": {"action": "create_rock", "reasoning": "structural"},
        "adopt_issue": {"action": "adopt_issue", "reasoning": "structural"},
    }

    for action in driver._supported_plan_actions():
        result = await driver.execute_plan(payloads[action])
        assert not result.startswith("Unsupported action"), action


@pytest.mark.asyncio
async def test_process_request_returns_stable_unsupported_action_error():
    """Layer: integration. Verifies prompt/executor parity guard for unsupported model-selected actions."""
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
    driver.skill = None
    driver.dialect = None

    class _Provider:
        async def complete(self, _messages):
            return SimpleNamespace(content='{"action":"delete_issue","reasoning":"requested delete"}')

    driver.provider = _Provider()

    response = await driver.process_request("settings")

    assert response.startswith("Unsupported action 'delete_issue'.")
    assert "assign_team (suggestion only" in response
    assert "structural changes: create_issue, create_epic, create_rock, adopt_issue" in response
