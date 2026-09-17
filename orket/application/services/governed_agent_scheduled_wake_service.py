from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from orket.application.services.governed_agent_wake_ingress_service import (
    GovernedAgentWakeSubmission,
)
from orket.core.contracts.governed_agent_schedule_records import (
    GovernedAgentScheduleEvaluationRecord,
    GovernedAgentScheduleEvaluationRequest,
    GovernedAgentScheduleEvaluationResult,
    GovernedAgentScheduleRepository,
    ScheduleCoalescingPolicy,
    ScheduleMissedPolicy,
)
from orket_extension_sdk import canonical_digest_sha256


@dataclass(frozen=True, slots=True)
class _ScheduleCandidate:
    occurrence_id: str
    scheduled_for_local: str
    scheduled_for_utc: str
    fold: int
    scheduled_at: datetime
    submission: GovernedAgentWakeSubmission


class GovernedAgentScheduledWakeService:
    """Evaluate one durable schedule window before any supervisor dispatch."""

    def __init__(
        self,
        *,
        repository: GovernedAgentScheduleRepository,
        notify_ready: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._notify_ready = notify_ready

    async def evaluate(
        self,
        *,
        schedule_id: str,
        payload: Mapping[str, Any],
    ) -> GovernedAgentScheduleEvaluationResult:
        evaluation = _evaluation_request(schedule_id=schedule_id, payload=payload)
        result = await self._repository.apply_evaluation(evaluation)
        if (
            result.status in {"enqueued", "idempotent"}
            and result.wake is not None
            and result.wake.state == "queued"
            and self._notify_ready is not None
        ):
            self._notify_ready()
        return result

    async def list_evaluations(
        self,
        *,
        schedule_id: str,
    ) -> tuple[GovernedAgentScheduleEvaluationRecord, ...]:
        return await self._repository.list_evaluations(schedule_id=_required_text(schedule_id, "E_AGENT_SCHEDULE_ID_REQUIRED"))


def governed_agent_schedule_evaluation_view(
    evaluation: GovernedAgentScheduleEvaluationRecord,
) -> dict[str, Any]:
    return {
        "evaluation_id": evaluation.evaluation_id,
        "schedule_id": evaluation.schedule_id,
        "evaluated_at_utc": evaluation.evaluated_at_utc,
        "request": dict(evaluation.request),
        "request_digest": evaluation.request_digest,
        "status": evaluation.status,
        "selected_occurrence_id": evaluation.selected_occurrence_id,
        "coalesced_occurrence_ids": list(evaluation.coalesced_occurrence_ids),
        "skipped_occurrence_ids": list(evaluation.skipped_occurrence_ids),
        "resulting_wake_id": evaluation.resulting_wake_id,
    }


def _evaluation_request(
    *,
    schedule_id: str,
    payload: Mapping[str, Any],
) -> GovernedAgentScheduleEvaluationRequest:
    allowed = {
        "evaluation_id", "timezone", "observed_at_utc", "misfire_grace_seconds",
        "missed_policy", "coalescing_policy", "occurrences",
    }
    if set(payload) - allowed:
        raise ValueError("E_AGENT_SCHEDULE_FIELD_UNKNOWN")
    normalized_schedule_id = _required_text(schedule_id, "E_AGENT_SCHEDULE_ID_REQUIRED")
    evaluation_id = _required_text(payload.get("evaluation_id"), "E_AGENT_SCHEDULE_EVALUATION_ID_REQUIRED")
    timezone_name = _required_text(payload.get("timezone"), "E_AGENT_SCHEDULE_TIMEZONE_REQUIRED")
    zone = _timezone(timezone_name)
    observed_at = _utc_datetime(payload.get("observed_at_utc"))
    grace = _grace_seconds(payload.get("misfire_grace_seconds"))
    missed_policy = _missed_policy(payload.get("missed_policy"))
    coalescing_policy = _coalescing_policy(payload.get("coalescing_policy"))
    candidates = _candidates(
        schedule_id=normalized_schedule_id,
        zone=zone,
        value=payload.get("occurrences"),
        observed_at=observed_at,
    )
    return _select_evaluation(
        evaluation_id=evaluation_id,
        schedule_id=normalized_schedule_id,
        timezone_name=timezone_name,
        observed_at=observed_at,
        grace=grace,
        missed_policy=missed_policy,
        coalescing_policy=coalescing_policy,
        candidates=candidates,
    )


def _select_evaluation(
    *,
    evaluation_id: str,
    schedule_id: str,
    timezone_name: str,
    observed_at: datetime,
    grace: int,
    missed_policy: ScheduleMissedPolicy,
    coalescing_policy: ScheduleCoalescingPolicy,
    candidates: tuple[_ScheduleCandidate, ...],
) -> GovernedAgentScheduleEvaluationRequest:
    missed = tuple(candidate for candidate in candidates if observed_at > candidate.scheduled_at + timedelta(seconds=grace))
    skipped = missed if missed_policy == "skip" else ()
    eligible = tuple(candidate for candidate in candidates if candidate not in skipped)
    selected = None if not eligible else eligible[-1]
    coalesced = () if selected is None else eligible[:-1]
    normalized_payload = _normalized_evaluation_payload(
        evaluation_id=evaluation_id,
        schedule_id=schedule_id,
        timezone_name=timezone_name,
        observed_at=observed_at,
        grace=grace,
        missed_policy=missed_policy,
        coalescing_policy=coalescing_policy,
        candidates=candidates,
        selected=selected,
        coalesced=coalesced,
        skipped=skipped,
    )
    selected_wake = None
    if selected is not None:
        trigger = _trigger_payload(normalized_payload, selected, selected in missed)
        selected_wake = selected.submission.to_request(
            source="scheduled",
            created_at_utc=_utc_text(observed_at),
            trigger=trigger,
        )
    return GovernedAgentScheduleEvaluationRequest(
        evaluation_id=evaluation_id,
        schedule_id=schedule_id,
        evaluated_at_utc=_utc_text(observed_at),
        request=normalized_payload,
        selected_wake=selected_wake,
    )


def _candidates(
    *,
    schedule_id: str,
    zone: ZoneInfo,
    value: object,
    observed_at: datetime,
) -> tuple[_ScheduleCandidate, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not 1 <= len(value) <= 100:
        raise ValueError("E_AGENT_SCHEDULE_OCCURRENCES_REQUIRED")
    candidates = tuple(
        _candidate(schedule_id=schedule_id, zone=zone, value=item)
        for item in value
    )
    ordered = tuple(sorted(candidates, key=lambda item: (item.scheduled_at, item.occurrence_id)))
    if len({item.scheduled_for_utc for item in ordered}) != len(ordered):
        raise ValueError("E_AGENT_SCHEDULE_OCCURRENCE_DUPLICATE")
    if any(item.scheduled_at > observed_at for item in ordered):
        raise ValueError("E_AGENT_SCHEDULE_OCCURRENCE_FUTURE")
    return ordered


def _candidate(
    *,
    schedule_id: str,
    zone: ZoneInfo,
    value: object,
) -> _ScheduleCandidate:
    if not isinstance(value, Mapping):
        raise ValueError("E_AGENT_SCHEDULE_OCCURRENCE_INVALID")
    allowed = {"scheduled_for_local", "fold", "target_kind", "target_run_id", "workload_id", "dispatch"}
    if set(value) - allowed:
        raise ValueError("E_AGENT_SCHEDULE_OCCURRENCE_FIELD_UNKNOWN")
    fold = _fold(value.get("fold"))
    local, scheduled_at = _localized_datetime(value.get("scheduled_for_local"), zone=zone, fold=fold)
    scheduled_for_utc = _utc_text(scheduled_at)
    occurrence_id = f"schedule-occurrence:{canonical_digest_sha256({'schedule_id': schedule_id, 'scheduled_for_utc': scheduled_for_utc})[:32]}"
    submission = GovernedAgentWakeSubmission.from_mapping(
        {
            "occurrence_id": occurrence_id,
            "target_kind": value.get("target_kind"),
            "target_run_id": value.get("target_run_id"),
            "workload_id": value.get("workload_id"),
            "dispatch": value.get("dispatch"),
        }
    )
    return _ScheduleCandidate(
        occurrence_id=occurrence_id,
        scheduled_for_local=local.isoformat(timespec="microseconds"),
        scheduled_for_utc=scheduled_for_utc,
        fold=fold,
        scheduled_at=scheduled_at,
        submission=submission,
    )


def _normalized_evaluation_payload(
    *,
    evaluation_id: str,
    schedule_id: str,
    timezone_name: str,
    observed_at: datetime,
    grace: int,
    missed_policy: ScheduleMissedPolicy,
    coalescing_policy: ScheduleCoalescingPolicy,
    candidates: tuple[_ScheduleCandidate, ...],
    selected: _ScheduleCandidate | None,
    coalesced: tuple[_ScheduleCandidate, ...],
    skipped: tuple[_ScheduleCandidate, ...],
) -> dict[str, Any]:
    return {
        "schema_version": "governed_agent_schedule_evaluation.v1",
        "evaluation_id": evaluation_id,
        "schedule_id": schedule_id,
        "timezone": timezone_name,
        "observed_at_utc": _utc_text(observed_at),
        "misfire_grace_seconds": grace,
        "missed_policy": missed_policy,
        "coalescing_policy": coalescing_policy,
        "occurrences": [_candidate_payload(candidate) for candidate in candidates],
        "selected_occurrence_id": None if selected is None else selected.occurrence_id,
        "coalesced_occurrence_ids": [item.occurrence_id for item in coalesced],
        "skipped_occurrence_ids": [item.occurrence_id for item in skipped],
    }


def _candidate_payload(candidate: _ScheduleCandidate) -> dict[str, Any]:
    return {
        "occurrence_id": candidate.occurrence_id,
        "scheduled_for_local": candidate.scheduled_for_local,
        "scheduled_for_utc": candidate.scheduled_for_utc,
        "fold": candidate.fold,
        "target_kind": candidate.submission.target_kind,
        "target_run_id": candidate.submission.target_run_id,
        "workload_id": candidate.submission.workload_id,
        "dispatch": dict(candidate.submission.dispatch),
    }


def _trigger_payload(
    evaluation: Mapping[str, Any],
    selected: _ScheduleCandidate,
    missed: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "governed_agent_schedule_trigger.v1",
        "evaluation_id": evaluation["evaluation_id"],
        "schedule_id": evaluation["schedule_id"],
        "timezone": evaluation["timezone"],
        "scheduled_for_local": selected.scheduled_for_local,
        "scheduled_for_utc": selected.scheduled_for_utc,
        "fold": selected.fold,
        "observed_at_utc": evaluation["observed_at_utc"],
        "misfire_grace_seconds": evaluation["misfire_grace_seconds"],
        "missed": missed,
        "missed_policy": evaluation["missed_policy"],
        "coalescing_policy": evaluation["coalescing_policy"],
        "coalesced_occurrence_ids": list(cast(list[str], evaluation["coalesced_occurrence_ids"])),
        "skipped_occurrence_ids": list(cast(list[str], evaluation["skipped_occurrence_ids"])),
    }


def _localized_datetime(value: object, *, zone: ZoneInfo, fold: int) -> tuple[datetime, datetime]:
    raw = _required_text(value, "E_AGENT_SCHEDULE_LOCAL_TIME_REQUIRED")
    try:
        local = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("E_AGENT_SCHEDULE_LOCAL_TIME_INVALID") from exc
    if local.tzinfo is not None:
        raise ValueError("E_AGENT_SCHEDULE_LOCAL_TIME_MUST_BE_NAIVE")
    first = local.replace(tzinfo=zone, fold=0)
    second = local.replace(tzinfo=zone, fold=1)
    ambiguous = first.utcoffset() != second.utcoffset()
    if not ambiguous and fold != 0:
        raise ValueError("E_AGENT_SCHEDULE_FOLD_NONCANONICAL")
    localized = local.replace(tzinfo=zone, fold=fold)
    scheduled_at = localized.astimezone(UTC)
    round_trip = scheduled_at.astimezone(zone)
    if round_trip.replace(tzinfo=None) != local or (ambiguous and round_trip.fold != fold):
        raise ValueError("E_AGENT_SCHEDULE_LOCAL_TIME_NONEXISTENT")
    return local, scheduled_at


def _utc_datetime(value: object) -> datetime:
    raw = _required_text(value, "E_AGENT_SCHEDULE_OBSERVED_AT_REQUIRED")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("E_AGENT_SCHEDULE_OBSERVED_AT_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("E_AGENT_SCHEDULE_OBSERVED_AT_NOT_UTC")
    return parsed.astimezone(UTC)


def _timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("E_AGENT_SCHEDULE_TIMEZONE_INVALID") from exc


def _grace_seconds(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 86_400:
        raise ValueError("E_AGENT_SCHEDULE_MISFIRE_GRACE_INVALID")
    return value


def _fold(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value not in {0, 1}:
        raise ValueError("E_AGENT_SCHEDULE_FOLD_INVALID")
    return value


def _missed_policy(value: object) -> ScheduleMissedPolicy:
    normalized = str(value or "").strip()
    if normalized not in {"skip", "fire_once"}:
        raise ValueError("E_AGENT_SCHEDULE_MISSED_POLICY_INVALID")
    return cast(ScheduleMissedPolicy, normalized)


def _coalescing_policy(value: object) -> ScheduleCoalescingPolicy:
    if str(value or "").strip() != "latest":
        raise ValueError("E_AGENT_SCHEDULE_COALESCING_POLICY_INVALID")
    return "latest"


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _required_text(value: object, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(code)
    return normalized
