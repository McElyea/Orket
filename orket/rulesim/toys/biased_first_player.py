from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..canonical import hash_state
from ..contracts import TerminalResult, TransitionResult


class BiasedFirstPlayerRuleSystem:
    def initial_state(self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]) -> dict[str, Any]:
        return {"winner": None, "phase": "agent_0", "agent_0_passed": False}

    def legal_actions(self, state: dict[str, Any], agent_id: str) -> list[dict[str, Any]]:
        phase = str(state.get("phase") or "")
        if phase == "agent_0" and agent_id == "agent_0":
            return [{"kind": "win"}, {"kind": "pass"}]
        if phase == "agent_1" and agent_id == "agent_1":
            return [{"kind": "win"}]
        return [{"kind": "wait"}]

    def apply_action(self, state: dict[str, Any], agent_id: str, action: dict[str, Any]) -> TransitionResult:
        next_state = deepcopy(state)
        kind = str(action.get("kind") or "")
        if agent_id == "agent_0":
            if kind == "win":
                next_state["winner"] = "agent_0"
            elif kind == "pass":
                next_state["phase"] = "agent_1"
                next_state["agent_0_passed"] = True
        elif agent_id == "agent_1" and kind == "win":
            next_state["winner"] = "agent_1"
        return TransitionResult(next_state=next_state)

    def is_terminal(self, state: dict[str, Any]) -> TerminalResult | None:
        winner = state.get("winner")
        if winner in {"agent_0", "agent_1"}:
            return TerminalResult(reason="win", winners=[str(winner)])
        return None

    def observe(self, state: dict[str, Any], agent_id: str) -> dict[str, Any]:
        return dict(state)

    def hash_state(self, state: dict[str, Any]) -> str:
        return hash_state(self.serialize_state(state))

    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "winner": state.get("winner"),
            "phase": str(state.get("phase") or ""),
            "agent_0_passed": bool(state.get("agent_0_passed", False)),
        }

    def serialize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return {"kind": str(action.get("kind", ""))}

    def action_key(self, action: dict[str, Any]) -> str:
        return str(action.get("kind", "unknown"))

