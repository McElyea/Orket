from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from orket.application.services.model_selection_service import ModelSelectionService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _selector(organization=None, preferences=None, user_settings=None):
    return await ModelSelectionService(environment=dict(os.environ)).prepare(
        organization, preferences or {}, user_settings or {})


def _org(process_rules: dict):
    return SimpleNamespace(
        architecture=SimpleNamespace(preferred_stack={}),
        process_rules=process_rules,
    )


# Layer: integration
async def test_operator_uses_user_preference():
    selector = await _selector(preferences={"models": {"operations_lead": "qwen2.5-coder:14b"}})

    selected = selector.select(role="operations_lead").final_model

    assert selected == "qwen2.5-coder:14b"


# Layer: integration
async def test_operator_env_override_precedence(monkeypatch):
    monkeypatch.setenv("ORKET_OPERATOR_MODEL", "llama3.3:70b")
    selector = await _selector(preferences={"models": {"operations_lead": "qwen2.5-coder:14b"}})

    selected = selector.select(role="operations_lead").final_model

    assert selected == "llama3.3:70b"


# Layer: integration
async def test_operator_uses_process_rule_preference_when_user_missing():
    selector = await _selector(
        organization=_org({"models": {"operations_lead": "deepseek-r1:32b"}}),
        preferences={},
    )

    selected = selector.select(role="operations_lead").final_model

    assert selected == "deepseek-r1:32b"


# Layer: integration
async def test_legacy_preferred_key_is_not_used():
    selector = await _selector(
        preferences={},
        user_settings={"preferred_operations_lead": "legacy-model:1b"},
    )

    selected = selector.select(role="operations_lead").final_model

    assert selected != "legacy-model:1b"
