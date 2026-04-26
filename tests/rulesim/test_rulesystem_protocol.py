from __future__ import annotations

import pytest

from orket.rulesim.contracts import RuleSystem
from orket.rulesim.toys import TOY_RULESYSTEMS, build_toy_rulesystem
from orket.rulesim.toys.loop import LoopRuleSystem, LoopState


def test_toy_rulesystem_registration_enforces_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies malformed toy registrations fail before runtime execution."""

    class MalformedRuleSystem:
        def initial_state(self, seed, scenario, ruleset, agents):  # type: ignore[no-untyped-def]
            return {}

    monkeypatch.setitem(TOY_RULESYSTEMS, "malformed", MalformedRuleSystem)

    with pytest.raises(TypeError, match="RuleSystem protocol"):
        build_toy_rulesystem("malformed")


def test_golden_determinism_is_loop_rulesystem_alias() -> None:
    """Layer: unit. Verifies golden determinism is a registry alias, not a behaviorless subclass."""
    rulesystem = build_toy_rulesystem("golden_determinism")

    assert isinstance(rulesystem, LoopRuleSystem)
    assert isinstance(rulesystem, RuleSystem)


def test_toy_action_kind_rejects_non_string_values() -> None:
    """Layer: unit. Verifies toy RuleSystems reject non-string action.kind instead of coercing it."""
    rulesystem = build_toy_rulesystem("loop")

    with pytest.raises(TypeError, match="action.kind"):
        rulesystem.serialize_action({"kind": 7})


def test_loop_rulesystem_uses_typed_immutable_state() -> None:
    """Layer: unit. Verifies toy state advances by replacement instead of mutating a dict."""
    rulesystem = build_toy_rulesystem("loop")

    state = rulesystem.initial_state(seed=1, scenario={}, ruleset={}, agents=["agent_0"])
    result = rulesystem.apply_action(state, "agent_0", {"kind": "advance"})

    assert isinstance(state, LoopState)
    assert isinstance(result.next_state, LoopState)
    assert state.tick == 0
    assert result.next_state.tick == 1
