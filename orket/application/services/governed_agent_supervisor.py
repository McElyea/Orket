from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal, Protocol

from orket.application.services.governed_agent_ports import GovernedAgentAuthorityStaleError
from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeAuthority,
    GovernedAgentWakeRecord,
    GovernedAgentWakeRepository,
)

LOGGER = logging.getLogger(__name__)
SupervisorCycleStatus = Literal[
    "empty",
    "capacity",
    "completed",
    "released",
    "recovery_required",
    "stale",
    "failed",
]


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeDispatchResult:
    status: Literal["completed", "released", "uncertain"]
    result_ref: str | None = None
    reason: str | None = None
    child_confirmed_stopped: bool = False
    effect_uncertainty: bool = False


@dataclass(frozen=True, slots=True)
class GovernedAgentSupervisorCycleResult:
    status: SupervisorCycleStatus
    wake_id: str | None
    fencing_generation: int | None
    detail: str | None = None


class GovernedAgentWakeClaimGuard:
    """Dispatcher-visible fence check required before every authoritative operation."""

    def __init__(
        self,
        *,
        repository: GovernedAgentWakeRepository,
        authority: GovernedAgentWakeAuthority,
        now_utc: Callable[[], str],
    ) -> None:
        self._repository = repository
        self.authority = authority
        self._now_utc = now_utc

    async def ensure_active(self) -> None:
        if not await self._repository.validate_claim(
            authority=self.authority,
            now_utc=self._now_utc(),
        ):
            raise GovernedAgentAuthorityStaleError("E_AGENT_WAKE_CLAIM_STALE")


class GovernedAgentWakeDispatcher(Protocol):
    async def dispatch(
        self,
        *,
        wake: GovernedAgentWakeRecord,
        guard: GovernedAgentWakeClaimGuard,
    ) -> GovernedAgentWakeDispatchResult: ...


class GovernedAgentSupervisorTaskOwner(Protocol):
    def track_background_task(self, task: asyncio.Task[object]) -> None: ...

    def release_background_task(self, task: asyncio.Task[object]) -> None: ...


class GovernedAgentSupervisor:
    """Event-driven owner of at most one bounded wake dispatch per cycle."""

    def __init__(
        self,
        *,
        repository: GovernedAgentWakeRepository,
        dispatcher: GovernedAgentWakeDispatcher,
        owner_id: str,
        max_active_claims: int,
        now_utc: Callable[[], str],
        lease_expires_at_utc: Callable[[str], str],
        idle_wait_seconds: float = 1.0,
        renewal_interval_seconds: float = 15.0,
    ) -> None:
        if (
            not owner_id.strip()
            or max_active_claims < 1
            or idle_wait_seconds <= 0
            or renewal_interval_seconds <= 0
        ):
            raise ValueError("E_AGENT_SUPERVISOR_CONFIGURATION_INVALID")
        self._repository = repository
        self._dispatcher = dispatcher
        self._owner_id = owner_id.strip()
        self._max_active_claims = max_active_claims
        self._now_utc = now_utc
        self._lease_expires_at_utc = lease_expires_at_utc
        self._idle_wait_seconds = idle_wait_seconds
        self._renewal_interval_seconds = renewal_interval_seconds
        self._notification = asyncio.Event()
        self._cycle_lock = asyncio.Lock()
        self._closing = False
        self._task: asyncio.Task[object] | None = None
        self._current_authority: GovernedAgentWakeAuthority | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def run_once(self) -> GovernedAgentSupervisorCycleResult:
        async with self._cycle_lock:
            return await self._run_once_unlocked()

    async def _run_once_unlocked(self) -> GovernedAgentSupervisorCycleResult:
        claim_now = self._now_utc()
        claim = await self._repository.claim_next(
            owner_id=self._owner_id,
            now_utc=claim_now,
            lease_expires_at_utc=self._lease_expires_at_utc(claim_now),
            max_active_claims=self._max_active_claims,
        )
        if claim.status == "empty":
            return GovernedAgentSupervisorCycleResult("empty", None, None)
        if claim.status == "capacity":
            return GovernedAgentSupervisorCycleResult("capacity", None, None)
        if claim.wake is None or claim.authority is None:
            raise RuntimeError("E_AGENT_WAKE_CLAIM_INCOMPLETE")
        wake = claim.wake
        authority = claim.authority
        self._current_authority = authority
        guard = GovernedAgentWakeClaimGuard(
            repository=self._repository,
            authority=authority,
            now_utc=self._now_utc,
        )
        try:
            await guard.ensure_active()
            result = await self._dispatch_with_renewal(wake, guard)
            await guard.ensure_active()
            return await self._publish_result(authority, result)
        except asyncio.CancelledError:
            await self._release_uncertain(authority, "supervisor_cancelled")
            raise
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            LOGGER.exception("Governed-agent wake dispatch failed", extra={"wake_id": wake.wake_id})
            transition = await self._release_uncertain(authority, f"dispatch_failed:{type(exc).__name__}")
            status: SupervisorCycleStatus = "failed" if transition else "stale"
            return GovernedAgentSupervisorCycleResult(
                status,
                wake.wake_id,
                authority.fencing_generation,
                str(exc),
            )
        finally:
            self._current_authority = None

    def start(self, task_owner: GovernedAgentSupervisorTaskOwner | None = None) -> asyncio.Task[object]:
        if self._closing:
            raise RuntimeError("E_AGENT_SUPERVISOR_CLOSED")
        if self.running:
            raise RuntimeError("E_AGENT_SUPERVISOR_ALREADY_RUNNING")
        task = asyncio.create_task(self._serve())
        self._task = task
        if task_owner is not None:
            task_owner.track_background_task(task)
            task.add_done_callback(task_owner.release_background_task)
        return task

    def notify(self) -> None:
        if not self._closing:
            self._notification.set()

    async def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._notification.set()
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._task = None

    async def _serve(self) -> None:
        while not self._closing:
            cycle = await self.run_once()
            if cycle.status not in {"empty", "capacity", "released"}:
                continue
            self._notification.clear()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._notification.wait(), timeout=self._idle_wait_seconds)

    async def _dispatch_with_renewal(
        self,
        wake: GovernedAgentWakeRecord,
        guard: GovernedAgentWakeClaimGuard,
    ) -> GovernedAgentWakeDispatchResult:
        dispatch_task = asyncio.create_task(
            self._dispatcher.dispatch(wake=wake, guard=guard),
            name=f"orket-agent-wake-dispatch:{wake.wake_id}",
        )
        renewal_task = asyncio.create_task(
            self._renew_claim(guard),
            name=f"orket-agent-wake-renewal:{wake.wake_id}",
        )
        try:
            done, _ = await asyncio.wait(
                {dispatch_task, renewal_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if dispatch_task in done:
                return await dispatch_task
            await renewal_task
            dispatch_task.cancel()
            with suppress(asyncio.CancelledError):
                await dispatch_task
            raise GovernedAgentAuthorityStaleError("E_AGENT_WAKE_CLAIM_RENEWAL_STALE")
        finally:
            for task in (dispatch_task, renewal_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(dispatch_task, renewal_task, return_exceptions=True)

    async def _renew_claim(self, guard: GovernedAgentWakeClaimGuard) -> None:
        while True:
            await asyncio.sleep(self._renewal_interval_seconds)
            now = self._now_utc()
            transition = await self._repository.renew_claim(
                authority=guard.authority,
                now_utc=now,
                lease_expires_at_utc=self._lease_expires_at_utc(now),
            )
            if transition.status not in {"applied", "idempotent"}:
                return

    async def _publish_result(
        self,
        authority: GovernedAgentWakeAuthority,
        result: GovernedAgentWakeDispatchResult,
    ) -> GovernedAgentSupervisorCycleResult:
        if result.status == "completed":
            if not str(result.result_ref or "").strip():
                raise ValueError("E_AGENT_WAKE_DISPATCH_RESULT_REF_REQUIRED")
            transition = await self._repository.complete_claim(
                authority=authority,
                now_utc=self._now_utc(),
                result_ref=str(result.result_ref),
            )
            status: SupervisorCycleStatus = "completed" if transition.status in {"applied", "idempotent"} else "stale"
        else:
            transition = await self._repository.release_claim(
                authority=authority,
                now_utc=self._now_utc(),
                reason=str(result.reason or result.status),
                child_confirmed_stopped=result.child_confirmed_stopped,
                effect_uncertainty=result.effect_uncertainty or result.status == "uncertain",
            )
            if transition.status == "stale":
                status = "stale"
            else:
                status = "released" if transition.wake is not None and transition.wake.state == "queued" else "recovery_required"
        return GovernedAgentSupervisorCycleResult(
            status,
            authority.wake_id,
            authority.fencing_generation,
            result.reason,
        )

    async def _release_uncertain(self, authority: GovernedAgentWakeAuthority, reason: str) -> bool:
        transition = await self._repository.release_claim(
            authority=authority,
            now_utc=self._now_utc(),
            reason=reason,
            child_confirmed_stopped=False,
            effect_uncertainty=True,
        )
        return transition.status == "applied"
