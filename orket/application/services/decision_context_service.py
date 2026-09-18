"""Capture small immutable configuration inputs before invoking strategy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orket.core.contracts.decision_inputs import LoopPolicyInputs, ScalarLimit


def _limit(value: Any) -> ScalarLimit:
    return value if isinstance(value, (str, int, float, bool)) else None


def capture_loop_policy_inputs(organization: Any, environment: Mapping[str, str]) -> LoopPolicyInputs:
    rules = getattr(organization, "process_rules", None)
    configured = rules.get("orchestrator_max_iterations") if isinstance(rules, dict) else None
    return LoopPolicyInputs(
        concurrency=_limit(environment.get("ORKET_ORCHESTRATOR_CONCURRENCY")),
        max_iterations=_limit(environment.get("ORKET_ORCHESTRATOR_MAX_ITERATIONS")),
        configured_max_iterations=_limit(configured),
        context_window=_limit(environment.get("ORKET_CONTEXT_WINDOW")),
    )
