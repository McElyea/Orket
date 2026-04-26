from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any

from ..canonical import hash_state
from ..contracts import TerminalResult, TransitionResult
from ._actions import require_action_kind


@dataclass(frozen=True)
class IllegalActionState:
    ticks: int = 0
    done: bool = False


def _coerce_state(state: Any) -> IllegalActionState:
    if isinstance(state, IllegalActionState):
        return state
    if isinstance(state, Mapping):
        return IllegalActionState(ticks=int(state.get("ticks", 0)), done=bool(state.get("done", False)))
    raise TypeError("IllegalActionRuleSystem state must be IllegalActionState or mapping")


class IllegalActionRuleSystem:
    def initial_state(
        self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]
    ) -> IllegalActionState:
        return IllegalActionState()

    def legal_actions(self, state: Any, agent_id: str) -> list[dict[str, Any]]:
        return [{"kind": "pass"}, {"kind": "move"}]

    def apply_action(self, state: Any, agent_id: str, action: dict[str, Any]) -> TransitionResult:
        current = _coerce_state(state)
        next_state = replace(current, ticks=current.ticks + 1, done=current.done or require_action_kind(action) == "pass")
        return TransitionResult(next_state=next_state)

    def is_terminal(self, state: Any) -> TerminalResult | None:
        if _coerce_state(state).done:
            return TerminalResult(reason="draw", winners=[])
        return None

    def observe(self, state: Any, agent_id: str) -> dict[str, Any]:
        current = _coerce_state(state)
        return {"ticks": current.ticks}

    def hash_state(self, state: Any) -> str:
        return hash_state(self.serialize_state(state))

    def serialize_state(self, state: Any) -> dict[str, Any]:
        return asdict(_coerce_state(state))

    def serialize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return {"kind": require_action_kind(action)}

    def action_key(self, action: dict[str, Any]) -> str:
        return require_action_kind(action)
