from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

from orket.application.services.governed_agent_wake_dispatcher import (
    GovernedAgentWakeDispatchEnvelope,
)
from orket.core.contracts.governed_agent_wake_records import (
    GovernedAgentWakeEnqueueResult,
    GovernedAgentWakeRepository,
    GovernedAgentWakeRequest,
    WakeSource,
)
from orket_extension_sdk import FrozenJson, canonical_digest_sha256


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeSubmission:
    occurrence_id: str
    target_kind: Literal["existing_run", "new_run"]
    target_run_id: str | None
    workload_id: str | None
    dispatch: FrozenJson

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> GovernedAgentWakeSubmission:
        allowed = {"occurrence_id", "target_kind", "target_run_id", "workload_id", "dispatch"}
        if set(payload) - allowed:
            raise ValueError("E_AGENT_API_WAKE_FIELD_UNKNOWN")
        occurrence_id = _required_text(payload.get("occurrence_id"), "E_AGENT_WAKE_OCCURRENCE_REQUIRED")
        target_kind = str(payload.get("target_kind") or "").strip()
        target_run_id = _optional_text(payload.get("target_run_id"))
        workload_id = _optional_text(payload.get("workload_id"))
        dispatch = payload.get("dispatch")
        if target_kind not in {"existing_run", "new_run"}:
            raise ValueError("E_AGENT_WAKE_TARGET_KIND_INVALID")
        if not isinstance(dispatch, Mapping):
            raise ValueError("E_AGENT_WAKE_DISPATCH_REQUIRED")
        if "trigger" in dispatch:
            raise ValueError("E_AGENT_WAKE_TRIGGER_RESERVED")
        envelope = GovernedAgentWakeDispatchEnvelope.from_payload(dispatch)
        request = envelope.request
        if target_kind == "existing_run" and (target_run_id != request.identity.run_id or workload_id is not None):
            raise ValueError("E_AGENT_WAKE_EXISTING_RUN_TARGET_INVALID")
        if target_kind == "new_run" and (workload_id is None or target_run_id is not None):
            raise ValueError("E_AGENT_WAKE_NEW_RUN_TARGET_INVALID")
        return cls(
            occurrence_id=occurrence_id,
            target_kind=cast(Literal["existing_run", "new_run"], target_kind),
            target_run_id=target_run_id,
            workload_id=workload_id,
            dispatch=FrozenJson.freeze(dict(dispatch)),
        )

    def to_request(
        self,
        *,
        source: WakeSource,
        created_at_utc: str,
        trigger: Mapping[str, Any] | None = None,
    ) -> GovernedAgentWakeRequest:
        identity = {
            "source": source,
            "occurrence_id": self.occurrence_id,
            "target_kind": self.target_kind,
            "target_run_id": self.target_run_id,
            "workload_id": self.workload_id,
        }
        dispatch = self.dispatch.thaw()
        if trigger is not None:
            dispatch["trigger"] = FrozenJson.freeze(dict(trigger)).thaw()
        digest = canonical_digest_sha256(identity)
        return GovernedAgentWakeRequest(
            wake_id=f"agent-wake:{digest[:32]}",
            source=source,
            target_kind=self.target_kind,
            target_run_id=self.target_run_id,
            workload_id=self.workload_id,
            occurrence_id=self.occurrence_id,
            deduplication_key=f"{source}:{self.occurrence_id}",
            payload=dispatch,
            created_at_utc=created_at_utc,
        )


class GovernedAgentWakeIngressService:
    """Validate and persist public wakes without owning execution authority."""

    def __init__(
        self,
        *,
        wake_repository: GovernedAgentWakeRepository,
        now_utc: Callable[[], str],
        notify_ready: Callable[[], None] | None = None,
    ) -> None:
        self._wakes = wake_repository
        self._now_utc = now_utc
        self._notify_ready = notify_ready

    async def enqueue(
        self,
        payload: Mapping[str, Any],
        *,
        source: Literal["api", "manual"],
    ) -> GovernedAgentWakeEnqueueResult:
        submission = GovernedAgentWakeSubmission.from_mapping(payload)
        request = submission.to_request(source=source, created_at_utc=self._now_utc())
        result = await self._wakes.enqueue(request)
        notify_wake_ready(result=result, notify_ready=self._notify_ready)
        return result


def notify_wake_ready(
    *,
    result: GovernedAgentWakeEnqueueResult,
    notify_ready: Callable[[], None] | None,
) -> None:
    if (
        result.status in {"enqueued", "idempotent"}
        and result.wake is not None
        and result.wake.state == "queued"
        and notify_ready is not None
    ):
        notify_ready()


def _required_text(value: object, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(code)
    return normalized


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
