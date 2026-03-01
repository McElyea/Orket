from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any, Protocol

from .types import Action, AgentId, Observation, State


@dataclass(frozen=True)
class TransitionResult:
    next_state: State
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


class RuleSystem(Protocol):
    def initial_state(self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[AgentId]) -> State:
        ...

    def legal_actions(self, state: State, agent_id: AgentId) -> list[Action]:
        ...

    def apply_action(self, state: State, agent_id: AgentId, action: Action) -> TransitionResult:
        ...

    def is_terminal(self, state: State) -> TerminalResult | None:
        ...

    def observe(self, state: State, agent_id: AgentId) -> Observation:
        ...

    def hash_state(self, state: State) -> str:
        ...

    def serialize_state(self, state: State) -> dict[str, Any]:
        ...

    def serialize_action(self, action: Action) -> dict[str, Any]:
        ...

    def action_key(self, action: Action) -> str:
        ...


class Strategy(Protocol):
    def select_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
        rng: Random,
        context: dict[str, Any],
    ) -> Action:
        ...

