from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any

from ..canonical import hash_state
from ..contracts import TerminalResult, TransitionResult
from ._actions import require_action_kind


@dataclass(frozen=True)
class BiasedFirstPlayerState:
    winner: str | None = None
    phase: str = "agent_0"
    agent_0_passed: bool = False


def _coerce_state(state: Any) -> BiasedFirstPlayerState:
    if isinstance(state, BiasedFirstPlayerState):
        return state
    if isinstance(state, Mapping):
        winner = state.get("winner")
        winner_token = str(winner or "")
        winner_text = winner_token if winner_token in {"agent_0", "agent_1"} else None
        return BiasedFirstPlayerState(
            winner=winner_text,
            phase=str(state.get("phase") or ""),
            agent_0_passed=bool(state.get("agent_0_passed", False)),
        )
    raise TypeError("BiasedFirstPlayerRuleSystem state must be BiasedFirstPlayerState or mapping")


class BiasedFirstPlayerRuleSystem:
    def initial_state(
        self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]
    ) -> BiasedFirstPlayerState:
        return BiasedFirstPlayerState()

    def legal_actions(self, state: Any, agent_id: str) -> list[dict[str, Any]]:
        phase = _coerce_state(state).phase
        if phase == "agent_0" and agent_id == "agent_0":
            return [{"kind": "win"}, {"kind": "pass"}]
        if phase == "agent_1" and agent_id == "agent_1":
            return [{"kind": "win"}]
        return [{"kind": "wait"}]

    def apply_action(self, state: Any, agent_id: str, action: dict[str, Any]) -> TransitionResult:
        current = _coerce_state(state)
        next_state = current
        kind = require_action_kind(action)
        if agent_id == "agent_0":
            if kind == "win":
                next_state = replace(current, winner="agent_0")
            elif kind == "pass":
                next_state = replace(current, phase="agent_1", agent_0_passed=True)
        elif agent_id == "agent_1" and kind == "win":
            next_state = replace(current, winner="agent_1")
        return TransitionResult(next_state=next_state)

    def is_terminal(self, state: Any) -> TerminalResult | None:
        winner = _coerce_state(state).winner
        if winner in {"agent_0", "agent_1"}:
            return TerminalResult(reason="win", winners=[str(winner)])
        return None

    def observe(self, state: Any, agent_id: str) -> dict[str, Any]:
        return self.serialize_state(state)

    def hash_state(self, state: Any) -> str:
        return hash_state(self.serialize_state(state))

    def serialize_state(self, state: Any) -> dict[str, Any]:
        return asdict(_coerce_state(state))

    def serialize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return {"kind": require_action_kind(action)}

    def action_key(self, action: dict[str, Any]) -> str:
        return require_action_kind(action)
