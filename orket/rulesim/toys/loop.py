from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any

from ..canonical import hash_state
from ..contracts import TerminalResult, TransitionResult
from ._actions import require_action_kind


@dataclass(frozen=True)
class LoopState:
    tick: int = 0


def _coerce_state(state: Any) -> LoopState:
    if isinstance(state, LoopState):
        return state
    if isinstance(state, Mapping):
        return LoopState(tick=int(state.get("tick", 0)))
    raise TypeError("LoopRuleSystem state must be LoopState or mapping")


class LoopRuleSystem:
    def initial_state(
        self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]
    ) -> LoopState:
        return LoopState()

    def legal_actions(self, state: Any, agent_id: str) -> list[dict[str, Any]]:
        return [{"kind": "advance"}]

    def apply_action(self, state: Any, agent_id: str, action: dict[str, Any]) -> TransitionResult:
        current = _coerce_state(state)
        next_state = replace(current, tick=(current.tick + 1) % 2)
        return TransitionResult(next_state=next_state, events=[], skip_agent=None, invalid=False, error=None)

    def is_terminal(self, state: Any) -> TerminalResult | None:
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
