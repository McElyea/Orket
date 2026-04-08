from __future__ import annotations

import pytest

from orket.decision_nodes.contracts import ApiRuntimeStrategyNode
from orket.decision_nodes.registry import DecisionNodeRegistry

pytestmark = pytest.mark.contract


def test_api_runtime_strategy_contract_excludes_runtime_factory_methods() -> None:
    """Layer: contract. Verifies API runtime strategy no longer advertises host-construction or session-id authority."""
    forbidden = {
        "create_session_id",
        "create_preview_builder",
        "create_chat_driver",
        "create_member_metrics_reader",
        "create_execution_pipeline",
        "create_engine",
        "create_file_tools",
    }
    assert forbidden.isdisjoint(set(dir(ApiRuntimeStrategyNode)))


def test_decision_node_registry_excludes_engine_and_pipeline_wiring_factories() -> None:
    """Layer: contract. Verifies decision-node registry no longer exposes engine bootstrap or pipeline wiring factory seams."""
    registry = DecisionNodeRegistry()

    assert not hasattr(registry, "resolve_engine_runtime")
    assert not hasattr(registry, "register_engine_runtime")
    assert not hasattr(registry, "resolve_pipeline_wiring")
    assert not hasattr(registry, "register_pipeline_wiring")
