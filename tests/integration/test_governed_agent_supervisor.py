# Layer: integration

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.application.services.api_runtime_container import ApiRuntimeContainer
from orket.application.services.governed_agent_supervisor import (
    GovernedAgentSupervisor,
    GovernedAgentWakeClaimGuard,
    GovernedAgentWakeDispatchResult,
)
from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeRecord,
    GovernedAgentWakeRequest,
)

pytestmark = pytest.mark.integration


class _Clock:
    def __init__(self, value: str = "2026-09-07T12:00:01Z") -> None:
        self.value = value

    def now(self) -> str:
        return self.value

    def lease_expiry(self, _: str) -> str:
        return "2026-09-07T12:01:01Z"


class _CompletingDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def dispatch(
        self,
        *,
        wake: GovernedAgentWakeRecord,
        guard: GovernedAgentWakeClaimGuard,
    ) -> GovernedAgentWakeDispatchResult:
        await guard.ensure_active()
        self.calls.append((wake.wake_id, guard.authority.fencing_generation))
        return GovernedAgentWakeDispatchResult(
            status="completed",
            result_ref=f"agent-run:{wake.wake_id}",
            child_confirmed_stopped=True,
        )


class _BlockingDispatcher:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.block = asyncio.Event()

    async def dispatch(
        self,
        *,
        wake: GovernedAgentWakeRecord,
        guard: GovernedAgentWakeClaimGuard,
    ) -> GovernedAgentWakeDispatchResult:
        del wake
        await guard.ensure_active()
        self.entered.set()
        await self.block.wait()
        return GovernedAgentWakeDispatchResult(status="released", child_confirmed_stopped=True)


class _TaskOwner:
    def __init__(self) -> None:
        self.tasks: set[asyncio.Task[Any]] = set()

    def track_background_task(self, task: asyncio.Task[object]) -> None:
        self.tasks.add(task)

    def release_background_task(self, task: asyncio.Task[object]) -> None:
        self.tasks.discard(task)


def _wake() -> GovernedAgentWakeRequest:
    return GovernedAgentWakeRequest(
        wake_id="wake-1",
        source="api",
        target_kind="new_run",
        target_run_id=None,
        workload_id="governed-report",
        occurrence_id="request-1",
        deduplication_key="api:governed-report:request-1",
        payload={"request_ref": "agent-request:1"},
        created_at_utc="2026-09-07T12:00:00Z",
    )


def _supervisor(
    repository: AsyncGovernedAgentWakeRepository,
    dispatcher: Any,
    clock: _Clock,
) -> GovernedAgentSupervisor:
    return GovernedAgentSupervisor(
        repository=repository,
        dispatcher=dispatcher,
        owner_id="supervisor-a",
        max_active_claims=1,
        now_utc=clock.now,
        lease_expires_at_utc=clock.lease_expiry,
        idle_wait_seconds=0.01,
    )


@pytest.mark.asyncio
async def test_bounded_cycle_completes_one_wake_with_fenced_result(tmp_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    await repository.enqueue(_wake())
    dispatcher = _CompletingDispatcher()
    supervisor = _supervisor(repository, dispatcher, _Clock())

    result = await supervisor.run_once()
    retained = await repository.get_wake(wake_id="wake-1")

    assert result.status == "completed"
    assert dispatcher.calls == [("wake-1", 1)]
    assert retained is not None
    assert retained.state == "completed"
    assert retained.result_ref == "agent-run:wake-1"


@pytest.mark.asyncio
async def test_cancellation_during_dispatch_fences_result_publication(tmp_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    await repository.enqueue(_wake())

    class CancellingDispatcher:
        async def dispatch(
            self,
            *,
            wake: GovernedAgentWakeRecord,
            guard: GovernedAgentWakeClaimGuard,
        ) -> GovernedAgentWakeDispatchResult:
            await guard.ensure_active()
            cancelled = await repository.cancel_wake(
                wake_id=wake.wake_id,
                expected_cancellation_epoch=0,
                cancellation_epoch=1,
                reason="operator_cancelled",
            )
            assert cancelled.status == "applied"
            return GovernedAgentWakeDispatchResult(
                status="completed",
                result_ref="agent-run:must-not-publish",
            )

    result = await _supervisor(repository, CancellingDispatcher(), _Clock()).run_once()
    retained = await repository.get_wake(wake_id="wake-1")

    assert result.status == "stale"
    assert retained is not None
    assert retained.state == "cancelled"
    assert retained.result_ref is None


@pytest.mark.asyncio
async def test_background_shutdown_releases_claim_as_uncertain_and_leaks_no_task(tmp_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    await repository.enqueue(_wake())
    dispatcher = _BlockingDispatcher()
    supervisor = _supervisor(repository, dispatcher, _Clock())
    owner = _TaskOwner()

    supervisor.start(owner)
    await asyncio.wait_for(dispatcher.entered.wait(), timeout=1)
    assert supervisor.running is True
    assert len(owner.tasks) == 1

    await supervisor.close()
    await asyncio.sleep(0)
    retained = await repository.get_wake(wake_id="wake-1")

    assert supervisor.running is False
    assert owner.tasks == set()
    assert retained is not None
    assert retained.state == "recovery_required"
    assert retained.uncertainty is True
    assert retained.claim_owner_id == "supervisor-a"
    assert retained.last_reason == "supervisor_cancelled"


@pytest.mark.asyncio
async def test_dispatch_failure_is_durable_recovery_truth(tmp_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    await repository.enqueue(_wake())

    class FailingDispatcher:
        async def dispatch(
            self,
            *,
            wake: GovernedAgentWakeRecord,
            guard: GovernedAgentWakeClaimGuard,
        ) -> GovernedAgentWakeDispatchResult:
            del wake
            await guard.ensure_active()
            raise RuntimeError("provider_disconnected")

    result = await _supervisor(repository, FailingDispatcher(), _Clock()).run_once()
    retained = await repository.get_wake(wake_id="wake-1")

    assert result.status == "failed"
    assert retained is not None
    assert retained.state == "recovery_required"
    assert retained.last_reason == "dispatch_failed:RuntimeError"


@pytest.mark.asyncio
async def test_long_dispatch_renews_claim_until_bounded_result_publication(tmp_path: Path) -> None:
    """Layer: integration. The supervisor renews ownership while one bounded dispatch is active."""
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    await repository.enqueue(replace(_wake(), created_at_utc=datetime.now(UTC).isoformat()))

    class SlowDispatcher:
        async def dispatch(
            self,
            *,
            wake: GovernedAgentWakeRecord,
            guard: GovernedAgentWakeClaimGuard,
        ) -> GovernedAgentWakeDispatchResult:
            await guard.ensure_active()
            await asyncio.sleep(0.14)
            await guard.ensure_active()
            return GovernedAgentWakeDispatchResult(
                status="completed",
                result_ref=f"agent-run:{wake.wake_id}",
                child_confirmed_stopped=True,
            )

    def now() -> str:
        return datetime.now(UTC).isoformat()

    def expiry(_: str) -> str:
        return (datetime.now(UTC) + timedelta(seconds=0.08)).isoformat()

    supervisor = GovernedAgentSupervisor(
        repository=repository,
        dispatcher=SlowDispatcher(),
        owner_id="renewing-supervisor",
        max_active_claims=1,
        now_utc=now,
        lease_expires_at_utc=expiry,
        idle_wait_seconds=0.01,
        renewal_interval_seconds=0.02,
    )

    result = await supervisor.run_once()
    retained = await repository.get_wake(wake_id="wake-1")

    assert result.status == "completed"
    assert retained is not None and retained.state == "completed"


@pytest.mark.asyncio
async def test_application_runtime_container_owns_supervisor_task_and_teardown(tmp_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    await repository.enqueue(_wake())
    dispatcher = _BlockingDispatcher()
    supervisor = _supervisor(repository, dispatcher, _Clock())

    class Engine:
        closed = False

        async def close(self) -> None:
            self.closed = True

    engine = Engine()
    container = ApiRuntimeContainer(
        project_root=tmp_path,
        api_runtime_node=object(),
        runtime_state=object(),
        api_runtime_host=object(),
        engine=engine,
    )
    container.register_owned_resource(supervisor)
    supervisor.start(container)
    await asyncio.wait_for(dispatcher.entered.wait(), timeout=1)

    await container.close()
    retained = await repository.get_wake(wake_id="wake-1")

    assert container.closed is True
    assert container.active_background_task_count == 0
    assert supervisor.running is False
    assert engine.closed is True
    assert retained is not None and retained.state == "recovery_required"
