from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any, Protocol, runtime_checkable

from .types import AgentId


@dataclass(frozen=True)
class TransitionResult:
    next_state: Any
    events: list[dict[str, Any]] = field(default_factory=list)
    skip_agent: AgentId | None = None
    invalid: bool = False
    error: str | None = None


@dataclass(frozen=True)
class TerminalResult:
    terminal: bool = True
    reason: str = "draw"
    winners: list[AgentId] = field(default_factory=list)
    scores: dict[AgentId, float] | None = None


@runtime_checkable
class RuleSystem(Protocol):
    def initial_state(
        self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[AgentId]
    ) -> Any: ...

    def legal_actions(self, state: Any, agent_id: AgentId) -> list[Any]: ...

    def apply_action(self, state: Any, agent_id: AgentId, action: Any) -> TransitionResult: ...

    def is_terminal(self, state: Any) -> TerminalResult | None: ...

    def observe(self, state: Any, agent_id: AgentId) -> Any: ...

    def hash_state(self, state: Any) -> str: ...

    def serialize_state(self, state: Any) -> dict[str, Any]: ...

    def serialize_action(self, action: Any) -> dict[str, Any]: ...

    def action_key(self, action: Any) -> str: ...


class Strategy(Protocol):
    def select_action(
        self,
        observation: Any,
        legal_actions: list[Any],
        rng: Random,
        context: dict[str, Any],
    ) -> Any: ...
