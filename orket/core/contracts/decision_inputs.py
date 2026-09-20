"""Immutable values supplied to strategy and provider construction boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt

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


class FailureEvaluationInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    issue_id: str
    retry_count: int
    max_retries: int
    error: str | None
    violations: tuple[str, ...]


class SuccessTurnInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    issue_id: str
    issue_status: CardStatus
    content: str
    seat_name: str
    is_review_turn: bool


class SuccessEvaluationInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    turn: SuccessTurnInput
    updated_issue_status: CardStatus


class FailureRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    action: str
    next_retry_count: StrictInt


class SuccessRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    remember_decision: StrictBool = False
    trigger_sandbox: StrictBool = False
    promote_code_review: StrictBool = False


class SuccessActions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    trigger_sandbox: StrictBool = False
    next_status: CardStatus | None = None
