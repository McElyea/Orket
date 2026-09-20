"""Immutable values supplied to strategy and provider construction boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from orket.core.types import CardStatus

ScalarLimit = str | int | float | bool | None


@dataclass(frozen=True)
class LoopPolicyInputs:
    concurrency: ScalarLimit = None
    max_iterations: ScalarLimit = None
    configured_max_iterations: ScalarLimit = None
    context_window: ScalarLimit = None


@dataclass(frozen=True)
class ModelClientOptions:
    temperature: float
    timeout: float


@dataclass(frozen=True)
class ToolSelectionInput:
    available_names: tuple[str, ...]


class PlanningCardInput(BaseModel):
    """Advisory card facts, with no borrowed runtime model or mutable payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    status: CardStatus
    seat: str = ""
    summary: str = ""
    priority: float = 2.0
    depends_on: tuple[str, ...] = ()


class PlanningInput(BaseModel):
    """Captured eligible facts; the application retains dispatch authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    backlog: tuple[PlanningCardInput, ...]
    independent_ready: tuple[PlanningCardInput, ...]
    target_issue_id: str | None = None


class RoutingSeatInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    roles: tuple[str, ...]


class RoutingInput(BaseModel):
    """Seat recommendation inputs in captured team insertion order."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    issue_id: str
    issue_seat: str
    is_review_turn: bool
    seats: tuple[RoutingSeatInput, ...]
