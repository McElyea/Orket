# Layer: integration

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.application.services.governed_agent_wake_ingress_service import (
    GovernedAgentWakeIngressService,
)
from orket.core.contracts.governed_agent_wake_records import (
    GovernedAgentWakeAuthority,
    GovernedAgentWakeRequest,
)
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_public_ingress_scopes_stable_identity_by_source(tmp_path: Path) -> None:
    """Layer: integration. Equal API and manual occurrences remain distinct durable wakes."""
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    ingress = GovernedAgentWakeIngressService(
        wake_repository=repository,
        now_utc=lambda: "2026-09-07T12:00:00Z",
    )
    payload = {
        "occurrence_id": "shared-occurrence",
        "target_kind": "new_run",
        "workload_id": "governed-agent-loop",
        "dispatch": {
            "schema_version": "governed_agent_wake_dispatch.v1",
            "request": agent_request(),
            "creation_timestamp_utc": "2026-09-07T12:00:00Z",
            "decision_timestamps_utc": ["2026-09-07T12:00:01Z", "2026-09-07T12:00:02Z"],
            "next_lease_expiries_utc": ["2026-09-07T12:01:00Z"],
        },
    }

    manual = await ingress.enqueue(payload, source="manual")
    api = await ingress.enqueue(payload, source="api")

    assert manual.status == api.status == "enqueued"
    assert manual.wake is not None and api.wake is not None
    assert manual.wake.wake_id != api.wake.wake_id
    assert {wake.source for wake in await repository.list_wakes()} == {"manual", "api"}


def _request(
    wake_id: str = "wake-1",
    *,
    deduplication_key: str = "manual:run-1:occurrence-1",
) -> GovernedAgentWakeRequest:
    return GovernedAgentWakeRequest(
        wake_id=wake_id,
        source="manual",
        target_kind="existing_run",
        target_run_id="run-1",
        workload_id=None,
        occurrence_id="occurrence-1",
        deduplication_key=deduplication_key,
        payload={"reason": "operator_requested"},
        created_at_utc="2026-09-07T12:00:00Z",
    )


@pytest.mark.asyncio
async def test_enqueue_is_durable_idempotent_and_conflict_detecting(tmp_path: Path) -> None:
    db_path = tmp_path / "agent.sqlite3"
    repository = AsyncGovernedAgentWakeRepository(db_path)
    request = _request()

    first = await repository.enqueue(request)
    duplicate = await AsyncGovernedAgentWakeRepository(db_path).enqueue(request)
    identity_conflict = await repository.enqueue(replace(request, payload={"reason": "changed"}))
    deduplication_conflict = await repository.enqueue(
        _request("wake-2", deduplication_key=request.deduplication_key)
    )

    assert first.status == "enqueued"
    assert duplicate.status == "idempotent"
    assert identity_conflict.status == "conflict"
    assert deduplication_conflict.status == "conflict"
    assert first.wake == duplicate.wake
    assert (await AsyncGovernedAgentWakeRepository(db_path).list_wakes()) == (first.wake,)


@pytest.mark.asyncio
async def test_unadmitted_sources_and_malformed_wakes_fail_closed(tmp_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    request = _request()

    with pytest.raises(ValueError, match="E_AGENT_WAKE_SOURCE_NOT_ADMITTED"):
        await repository.enqueue(replace(request, source=cast(Any, "scheduled")))
    with pytest.raises(ValueError, match="E_AGENT_WAKE_SOURCE_NOT_ADMITTED"):
        await repository.enqueue(replace(request, source=cast(Any, "webhook")))
    with pytest.raises(ValueError, match="E_AGENT_WAKE_EXISTING_RUN_TARGET_INVALID"):
        await repository.enqueue(replace(request, target_run_id=None))
    with pytest.raises(ValueError, match="E_AGENT_WAKE_TIMESTAMP_NOT_UTC"):
        await repository.enqueue(replace(request, created_at_utc="2026-09-07T12:00:00"))
    with pytest.raises(ValueError, match="E_AGENT_WAKE_PAYLOAD_NOT_SERIALIZABLE"):
        await repository.enqueue(replace(request, payload={"invalid": object()}))


@pytest.mark.asyncio
async def test_competing_repositories_obtain_one_claim_and_stale_owner_is_fenced(tmp_path: Path) -> None:
    db_path = tmp_path / "agent.sqlite3"
    first_repository = AsyncGovernedAgentWakeRepository(db_path)
    second_repository = AsyncGovernedAgentWakeRepository(db_path)
    await first_repository.enqueue(_request())

    claims = await asyncio.gather(
        first_repository.claim_next(
            owner_id="supervisor-a",
            now_utc="2026-09-07T12:00:01Z",
            lease_expires_at_utc="2026-09-07T12:01:01Z",
            max_active_claims=2,
        ),
        second_repository.claim_next(
            owner_id="supervisor-b",
            now_utc="2026-09-07T12:00:01Z",
            lease_expires_at_utc="2026-09-07T12:01:01Z",
            max_active_claims=2,
        ),
    )

    claimed = [claim for claim in claims if claim.status == "claimed"]
    assert len(claimed) == 1
    authority = claimed[0].authority
    assert authority is not None
    claim_retry = await first_repository.claim_next(
        owner_id=authority.owner_id,
        now_utc="2026-09-07T12:00:02Z",
        lease_expires_at_utc="2026-09-07T12:01:02Z",
        max_active_claims=2,
    )
    assert claim_retry.status == "idempotent"
    assert claim_retry.authority == authority
    assert await first_repository.validate_claim(
        authority=authority,
        now_utc="2026-09-07T12:00:02Z",
    )

    released = await first_repository.release_claim(
        authority=authority,
        now_utc="2026-09-07T12:00:02Z",
        reason="bounded_action_complete_without_terminal_result",
        child_confirmed_stopped=True,
        effect_uncertainty=False,
    )
    release_retry = await first_repository.release_claim(
        authority=authority,
        now_utc="2026-09-07T12:00:02Z",
        reason="bounded_action_complete_without_terminal_result",
        child_confirmed_stopped=True,
        effect_uncertainty=False,
    )
    reclaimed = await second_repository.claim_next(
        owner_id="supervisor-b",
        now_utc="2026-09-07T12:00:03Z",
        lease_expires_at_utc="2026-09-07T12:01:03Z",
        max_active_claims=2,
    )

    assert released.wake is not None and released.wake.state == "queued"
    assert release_retry.status == "idempotent"
    assert reclaimed.authority is not None
    assert reclaimed.authority.fencing_generation == authority.fencing_generation + 1
    await _assert_stale_completion_fenced(
        first_repository,
        second_repository,
        stale_authority=authority,
        active_authority=reclaimed.authority,
    )


async def _assert_stale_completion_fenced(
    first_repository: AsyncGovernedAgentWakeRepository,
    second_repository: AsyncGovernedAgentWakeRepository,
    *,
    stale_authority: GovernedAgentWakeAuthority,
    active_authority: GovernedAgentWakeAuthority,
) -> None:
    assert not await first_repository.validate_claim(
        authority=stale_authority,
        now_utc="2026-09-07T12:00:04Z",
    )
    accepted_completion = await second_repository.complete_claim(
        authority=active_authority,
        now_utc="2026-09-07T12:00:04Z",
        result_ref="agent-result:shared",
    )
    accepted_retry = await second_repository.complete_claim(
        authority=active_authority,
        now_utc="2026-09-07T12:00:04Z",
        result_ref="agent-result:shared",
    )
    stale_completion = await first_repository.complete_claim(
        authority=stale_authority,
        now_utc="2026-09-07T12:00:04Z",
        result_ref="agent-result:shared",
    )
    assert accepted_completion.status == "applied"
    assert accepted_retry.status == "idempotent"
    assert stale_completion.status == "stale"


@pytest.mark.asyncio
async def test_expired_claim_requires_confirmed_recovery_before_redispatch(tmp_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    await repository.enqueue(_request())
    first = await repository.claim_next(
        owner_id="supervisor-a",
        now_utc="2026-09-07T12:00:01Z",
        lease_expires_at_utc="2026-09-07T12:00:02Z",
        max_active_claims=1,
    )
    assert first.authority is not None

    expired_release = await repository.release_claim(
        authority=first.authority,
        now_utc="2026-09-07T12:00:03Z",
        reason="old_worker_finished_after_expiry",
        child_confirmed_stopped=True,
        effect_uncertainty=False,
    )
    blocked = await repository.claim_next(
        owner_id="supervisor-b",
        now_utc="2026-09-07T12:00:04Z",
        lease_expires_at_utc="2026-09-07T12:01:04Z",
        max_active_claims=1,
    )
    retained = await repository.get_wake(wake_id="wake-1")

    assert expired_release.wake is not None
    assert expired_release.wake.state == "recovery_required"
    assert expired_release.wake.claim_owner_id == "supervisor-a"
    assert expired_release.wake.lease_expires_at_utc == "2026-09-07T12:00:02.000000Z"
    assert blocked.status == "empty"
    assert retained is not None
    assert retained.state == "recovery_required"
    assert retained.uncertainty is True
    refused = await repository.recover_expired_claim(
        wake_id="wake-1",
        expected_fencing_generation=first.authority.fencing_generation,
        child_confirmed_stopped=False,
        effect_uncertainty_cleared=True,
        reason="old_worker_not_stopped",
    )
    assert refused.status == "conflict"

    recovered = await repository.recover_expired_claim(
        wake_id="wake-1",
        expected_fencing_generation=first.authority.fencing_generation,
        child_confirmed_stopped=True,
        effect_uncertainty_cleared=True,
        reason="reconciled_and_stopped",
    )
    recovery_retry = await repository.recover_expired_claim(
        wake_id="wake-1",
        expected_fencing_generation=first.authority.fencing_generation,
        child_confirmed_stopped=True,
        effect_uncertainty_cleared=True,
        reason="reconciled_and_stopped",
    )
    second = await repository.claim_next(
        owner_id="supervisor-b",
        now_utc="2026-09-07T12:00:05Z",
        lease_expires_at_utc="2026-09-07T12:01:05Z",
        max_active_claims=1,
    )

    assert recovered.wake is not None and recovered.wake.state == "queued"
    assert recovery_retry.status == "idempotent"
    assert second.status == "claimed"
    assert second.authority is not None
    assert second.authority.fencing_generation == first.authority.fencing_generation + 1


@pytest.mark.asyncio
async def test_backpressure_renewal_and_cancellation_are_compare_and_set(tmp_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(tmp_path / "agent.sqlite3")
    await repository.enqueue(_request())
    await repository.enqueue(_request("wake-2", deduplication_key="manual:run-1:occurrence-2"))
    first = await repository.claim_next(
        owner_id="supervisor-a",
        now_utc="2026-09-07T12:00:01Z",
        lease_expires_at_utc="2026-09-07T12:01:01Z",
        max_active_claims=1,
    )
    assert first.authority is not None
    backpressured = await repository.claim_next(
        owner_id="supervisor-b",
        now_utc="2026-09-07T12:00:02Z",
        lease_expires_at_utc="2026-09-07T12:01:02Z",
        max_active_claims=1,
    )
    renewed = await repository.renew_claim(
        authority=first.authority,
        now_utc="2026-09-07T12:00:03Z",
        lease_expires_at_utc="2026-09-07T12:02:03Z",
    )
    renewal_retry = await repository.renew_claim(
        authority=first.authority,
        now_utc="2026-09-07T12:00:03Z",
        lease_expires_at_utc="2026-09-07T12:02:03Z",
    )
    cancelled = await repository.cancel_wake(
        wake_id="wake-1",
        expected_cancellation_epoch=0,
        cancellation_epoch=1,
        reason="operator_cancelled",
    )
    uncertain_capacity = await repository.claim_next(
        owner_id="supervisor-b",
        now_utc="2026-09-07T12:00:04Z",
        lease_expires_at_utc="2026-09-07T12:01:04Z",
        max_active_claims=1,
    )

    assert backpressured.status == "capacity"
    assert renewed.status == "applied"
    assert renewal_retry.status == "idempotent"
    assert cancelled.status == "applied"
    assert cancelled.wake is not None and cancelled.wake.state == "cancelled"
    assert cancelled.wake.uncertainty is True
    assert uncertain_capacity.status == "capacity"
    assert not await repository.validate_claim(
        authority=first.authority,
        now_utc="2026-09-07T12:00:04Z",
    )
