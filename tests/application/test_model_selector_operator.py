from __future__ import annotations

from types import SimpleNamespace

from orket.orchestration.models import ModelSelector


def _org(process_rules: dict):
    return SimpleNamespace(
        architecture=SimpleNamespace(preferred_stack={}),
        process_rules=process_rules,
    )


def test_operator_uses_user_preference():
    selector = ModelSelector(preferences={"models": {"operations_lead": "qwen2.5-coder:14b"}})

    selected = selector.select(role="operations_lead")

    assert selected == "qwen2.5-coder:14b"


def test_operator_env_override_precedence(monkeypatch):
    monkeypatch.setenv("ORKET_OPERATOR_MODEL", "llama3.3:70b")
    selector = ModelSelector(preferences={"models": {"operations_lead": "qwen2.5-coder:14b"}})

    selected = selector.select(role="operations_lead")

    assert selected == "llama3.3:70b"


def test_operator_uses_process_rule_preference_when_user_missing():
    selector = ModelSelector(
        organization=_org({"models": {"operations_lead": "deepseek-r1:32b"}}),
        preferences={},
    )

    selected = selector.select(role="operations_lead")

    assert selected == "deepseek-r1:32b"


def test_legacy_preferred_key_is_not_used():
    selector = ModelSelector(
        preferences={},
        user_settings={"preferred_operations_lead": "legacy-model:1b"},
    )

    selected = selector.select(role="operations_lead")

    assert selected != "legacy-model:1b"
