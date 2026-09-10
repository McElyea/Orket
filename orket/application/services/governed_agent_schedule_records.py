from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeRecord,
    GovernedAgentWakeRequest,
)

ScheduleMissedPolicy = Literal["skip", "fire_once"]
ScheduleCoalescingPolicy = Literal["latest"]
ScheduleEvaluationStatus = Literal["enqueued", "idempotent", "skipped", "conflict"]


@dataclass(frozen=True, slots=True)
class GovernedAgentScheduleEvaluationRequest:
    evaluation_id: str
    schedule_id: str
    evaluated_at_utc: str
    request: Mapping[str, Any]
    selected_wake: GovernedAgentWakeRequest | None


@dataclass(frozen=True, slots=True)
class GovernedAgentScheduleEvaluationRecord:
    evaluation_id: str
    schedule_id: str
    evaluated_at_utc: str
    request: Mapping[str, Any]
    request_digest: str
    status: ScheduleEvaluationStatus
    selected_occurrence_id: str | None
    coalesced_occurrence_ids: tuple[str, ...]
    skipped_occurrence_ids: tuple[str, ...]
    resulting_wake_id: str | None


@dataclass(frozen=True, slots=True)
class GovernedAgentScheduleEvaluationResult:
    status: ScheduleEvaluationStatus
    evaluation: GovernedAgentScheduleEvaluationRecord
    wake: GovernedAgentWakeRecord | None


class GovernedAgentScheduleRepository(Protocol):
    async def apply_evaluation(
        self,
        request: GovernedAgentScheduleEvaluationRequest,
    ) -> GovernedAgentScheduleEvaluationResult: ...

    async def list_evaluations(
        self,
        *,
        schedule_id: str,
    ) -> tuple[GovernedAgentScheduleEvaluationRecord, ...]: ...

    async def get_evaluation(
        self,
        *,
        evaluation_id: str,
    ) -> GovernedAgentScheduleEvaluationRecord | None: ...
