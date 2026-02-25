from __future__ import annotations

import pytest

from orket.decision_nodes.registry import DecisionNodeRegistry


class _StubPlanner:
    def create_parent_context(self, epic, model_selector):
        return {}

    def build_conductor_skills(self, team):
        return []

    def route_skill(self, issue):
        return None

    def fallback_role(self, fallback_order):
        return "architect"

    def should_replan(self, issue, turn_result):
        return False


def test_register_module_nodes_registers_planner_slot():
    registry = DecisionNodeRegistry()
    planner = _StubPlanner()
    registry.register_module_nodes("module.alpha", {"planner": planner})
    org = type("Org", (), {"process_rules": {"planner_node": "module.alpha"}})()
    assert registry.resolve_planner(org) is planner


def test_register_module_nodes_rejects_unknown_slot():
    registry = DecisionNodeRegistry()
    with pytest.raises(ValueError):
        registry.register_module_nodes("module.alpha", {"unknown_slot": object()})

