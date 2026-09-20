"""Immutable values supplied to strategy and provider construction boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt

from orket.core.domain.sandbox import PortAllocation
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


class SeatPolicyInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    seat_name: str
    issue: PlanningCardInput | None
    turn_status: CardStatus
    required_read_paths: tuple[str, ...]
    required_write_paths: tuple[str, ...]


class GuardReviewInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    rationale: str
    violations: tuple[str, ...]
    remediation_actions: tuple[str, ...]


class GuardReviewDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    valid: StrictBool
    reason: str | None = None


class NoCandidateOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    is_done: StrictBool
    event_name: str | None = None
    reason: str | None = None


def validate_guard_review_input(inputs: GuardReviewInput) -> dict[str, object]:
    if not inputs.rationale.strip():
        return {"valid": False, "reason": "missing_rationale"}
    if not any(action.strip() for action in inputs.remediation_actions):
        return {"valid": False, "reason": "missing_remediation_actions"}
    return {"valid": True, "reason": None}


class SandboxPortInput(PortAllocation):
    """Frozen projection of the authoritative port fields; no allocation ownership."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SandboxComposeInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    rock_id: str
    tech_stack: str
    ports: SandboxPortInput
