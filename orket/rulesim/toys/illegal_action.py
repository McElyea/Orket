from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..canonical import hash_state
from ..contracts import TerminalResult, TransitionResult


class IllegalActionRuleSystem:
    def initial_state(self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]) -> dict[str, Any]:
        return {"ticks": 0, "done": False}

    def legal_actions(self, state: dict[str, Any], agent_id: str) -> list[dict[str, Any]]:
        return [{"kind": "pass"}, {"kind": "move"}]

    def apply_action(self, state: dict[str, Any], agent_id: str, action: dict[str, Any]) -> TransitionResult:
        next_state = deepcopy(state)
        next_state["ticks"] = int(next_state.get("ticks", 0)) + 1
        if action.get("kind") == "pass":
            next_state["done"] = True
        return TransitionResult(next_state=next_state)

    def is_terminal(self, state: dict[str, Any]) -> TerminalResult | None:
        if bool(state.get("done")):
            return TerminalResult(reason="draw", winners=[])
        return None

    def observe(self, state: dict[str, Any], agent_id: str) -> dict[str, Any]:
        return {"ticks": int(state.get("ticks", 0))}

    def hash_state(self, state: dict[str, Any]) -> str:
        return hash_state(self.serialize_state(state))

    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"ticks": int(state.get("ticks", 0)), "done": bool(state.get("done", False))}

    def serialize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return {"kind": str(action.get("kind", ""))}

    def action_key(self, action: dict[str, Any]) -> str:
        return str(action.get("kind", "unknown"))

