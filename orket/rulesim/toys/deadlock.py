from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..canonical import hash_state
from ..contracts import TerminalResult, TransitionResult


class DeadlockRuleSystem:
    def initial_state(self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]) -> dict[str, Any]:
        return {"ticks": 0}

    def legal_actions(self, state: dict[str, Any], agent_id: str) -> list[dict[str, Any]]:
        if agent_id == "agent_0":
            return [{"kind": "pass"}]
        return []

    def apply_action(self, state: dict[str, Any], agent_id: str, action: dict[str, Any]) -> TransitionResult:
        next_state = deepcopy(state)
        next_state["ticks"] = int(next_state.get("ticks", 0)) + 1
        return TransitionResult(next_state=next_state)

    def is_terminal(self, state: dict[str, Any]) -> TerminalResult | None:
        return None

    def observe(self, state: dict[str, Any], agent_id: str) -> dict[str, Any]:
        return {"ticks": int(state.get("ticks", 0))}

    def hash_state(self, state: dict[str, Any]) -> str:
        return hash_state(self.serialize_state(state))

    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"ticks": int(state.get("ticks", 0))}

    def serialize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return {"kind": str(action.get("kind", ""))}

    def action_key(self, action: dict[str, Any]) -> str:
        return str(action.get("kind", "unknown"))

