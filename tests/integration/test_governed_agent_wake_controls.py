# Layer: integration

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_governed_agent_wake_control_repository import (
    AsyncGovernedAgentWakeControlRepository,
)
from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.adapters.storage.governed_agent_replay_store import GovernedAgentReplayStore
from orket.application.services.governed_agent_inspection_service import (
    GovernedAgentInspectionService,
)
from orket.core.contracts import RunRecord
from orket.core.contracts.governed_agent_wake_records import (
    GovernedAgentWakeCancellationRequest,
    GovernedAgentWakeRecoveryRequest,
    GovernedAgentWakeRequest,
    WakeRecoveryResolution,
)
from orket.core.domain import RunState

pytestmark = pytest.mark.integration


def _wake(wake_id: str, occurrence: str) -> GovernedAgentWakeRequest:
    return GovernedAgentWakeRequest(
        wake_id=wake_id,
        source="manual",
        target_kind="existing_run",
        target_run_id="run-1",
        workload_id=None,
        occurrence_id=occurrence,
        deduplication_key=f"manual:run-1:{occurrence}",
        payload={"reason": "operator_requested"},
        created_at_utc="2026-09-07T12:00:00Z",
    )


def _cancellation(action_id: str = "wake-action:cancel-1") -> GovernedAgentWakeCancellationRequest:
    return GovernedAgentWakeCancellationRequest(
        action_id=action_id,
        wake_id="wake-1",
        actor_ref="operator:test",
        timestamp_utc="2026-09-07T12:00:02Z",
        reason="operator_cancelled",
        expected_cancellation_epoch=0,
        cancellation_epoch=1,
    )


def _recovery(
    action_id: str,
    *,
    resolution: WakeRecoveryResolution = "confirm_cancelled",
    child_stopped: bool = True,
) -> GovernedAgentWakeRecoveryRequest:
    return GovernedAgentWakeRecoveryRequest(
        action_id=action_id,
        wake_id="wake-1",
        actor_ref="operator:test",
        timestamp_utc="2026-09-07T12:00:03Z",
        reason="reconciled_child_and_effects",
        expected_fencing_generation=1,
        resolution=resolution,
        child_confirmed_stopped=child_stopped,
        effect_uncertainty_cleared=True,
        evidence_refs=("process-reap:123", "effect-reconciliation:run-1"),
    )


@pytest.mark.asyncio
async def test_cancelled_claim_retains_capacity_until_evidenced_resolution(tmp_path: Path) -> None:
    """Layer: integration. Claimed cancellation stays conservative until a durable recovery action clears it."""
    db_path = tmp_path / "agent.sqlite3"
    wakes = AsyncGovernedAgentWakeRepository(db_path)
    controls = AsyncGovernedAgentWakeControlRepository(db_path)
    await wakes.enqueue(_wake("wake-1", "occurrence-1"))
    await wakes.enqueue(_wake("wake-2", "occurrence-2"))
    first = await wakes.claim_next(
        owner_id="supervisor-a",
        now_utc="2026-09-07T12:00:01Z",
        lease_expires_at_utc="2026-09-07T12:01:01Z",
        max_active_claims=1,
    )
    assert first.authority is not None

    cancelled = await controls.apply_cancellation(_cancellation())
    blocked = await wakes.claim_next(
        owner_id="supervisor-b",
        now_utc="2026-09-07T12:00:02Z",
        lease_expires_at_utc="2026-09-07T12:01:02Z",
        max_active_claims=1,
    )
    refused = await controls.apply_recovery(_recovery("wake-action:refused", child_stopped=False))
    recovered_request = _recovery("wake-action:recover-1")
    recovered = await controls.apply_recovery(recovered_request)
    replayed = await controls.apply_recovery(recovered_request)
    contradicted = await controls.apply_recovery(replace(recovered_request, reason="contradiction"))
    second = await wakes.claim_next(
        owner_id="supervisor-b",
        now_utc="2026-09-07T12:00:04Z",
        lease_expires_at_utc="2026-09-07T12:01:04Z",
        max_active_claims=1,
    )

    assert cancelled.status == "applied" and cancelled.wake is not None
    assert cancelled.wake.state == "cancelled" and cancelled.wake.uncertainty is True
    assert blocked.status == "capacity" and refused.status == "conflict"
    assert (recovered.status, replayed.status) == ("applied", "idempotent")
    assert recovered.wake is not None and recovered.wake.uncertainty is False
    assert contradicted.status == "conflict" and second.status == "claimed"
    actions = await controls.list_actions(wake_id="wake-1")
    assert {action.action_id: action.status for action in actions} == {
        "wake-action:cancel-1": "applied",
        "wake-action:refused": "conflict",
        "wake-action:recover-1": "applied",
    }
    recovery_action = next(action for action in actions if action.action_id == "wake-action:recover-1")
    assert recovery_action.request["evidence_refs"] == [
        "process-reap:123",
        "effect-reconciliation:run-1",
    ]
    operator_actions = await AsyncControlPlaneRecordRepository(db_path).list_operator_actions(
        target_ref="wake-1"
    )
    assert {action.action_id: action.result for action in operator_actions} == {
        "wake-action:cancel-1": "applied",
        "wake-action:refused": "conflict",
        "wake-action:recover-1": "applied",
    }
    recovery_operator_action = next(
        action for action in operator_actions if action.action_id == "wake-action:recover-1"
    )
    assert recovery_operator_action.receipt_refs == [
        "governed-agent-wake-action:wake-action:recover-1",
        "process-reap:123",
        "effect-reconciliation:run-1",
    ]


@pytest.mark.asyncio
async def test_evidenced_recovery_requeues_expired_claim(tmp_path: Path) -> None:
    """Layer: integration. Recovery-required work is requeued only with matching fence and evidence."""
    db_path = tmp_path / "agent.sqlite3"
    wakes = AsyncGovernedAgentWakeRepository(db_path)
    controls = AsyncGovernedAgentWakeControlRepository(db_path)
    await wakes.enqueue(_wake("wake-1", "occurrence-1"))
    first = await wakes.claim_next(
        owner_id="supervisor-a",
        now_utc="2026-09-07T12:00:01Z",
        lease_expires_at_utc="2026-09-07T12:00:02Z",
        max_active_claims=1,
    )
    assert first.authority is not None
    await wakes.release_claim(
        authority=first.authority,
        now_utc="2026-09-07T12:00:03Z",
        reason="expired_worker_returned",
        child_confirmed_stopped=True,
        effect_uncertainty=False,
    )

    recovered = await controls.apply_recovery(_recovery("wake-action:requeue-1", resolution="requeue"))
    reclaimed = await wakes.claim_next(
        owner_id="supervisor-b",
        now_utc="2026-09-07T12:00:04Z",
        lease_expires_at_utc="2026-09-07T12:01:04Z",
        max_active_claims=1,
    )

    assert recovered.status == "applied" and recovered.wake is not None
    assert recovered.wake.state == "queued" and recovered.wake.uncertainty is False
    assert reclaimed.status == "claimed" and reclaimed.authority is not None
    assert reclaimed.authority.fencing_generation == 2


@pytest.mark.asyncio
# Layer: integration
async def test_run_inspection_composes_durable_wake_control_receipts(tmp_path: Path) -> None:
    """Layer: integration. Run inspection exposes wake state and the durable action that produced it."""
    db_path = tmp_path / "agent.sqlite3"
    execution = AsyncControlPlaneExecutionRepository(db_path)
    iterations = AsyncGovernedAgentRepository(db_path)
    records = AsyncControlPlaneRecordRepository(db_path)
    wakes = AsyncGovernedAgentWakeRepository(db_path)
    controls = AsyncGovernedAgentWakeControlRepository(db_path)
    await execution.save_run_record(record=_run_record())
    await wakes.enqueue(_wake("wake-1", "occurrence-1"))
    await controls.apply_cancellation(_cancellation())
    inspector = GovernedAgentInspectionService(
        replay_repository=GovernedAgentReplayStore(db_path),
        iteration_repository=iterations,
        call_repository=iterations,
        wake_repository=wakes,
        wake_control_repository=controls,
        record_repository=records,
    )

    inspection = await inspector.inspect(run_id="run-1")

    assert inspection is not None
    assert inspection["wakes"][0]["state"] == "cancelled"
    assert inspection["wake_actions"][0]["action_id"] == "wake-action:cancel-1"
    assert inspection["wake_actions"][0]["request"]["reason"] == "operator_cancelled"
    assert inspection["operator_actions"][0]["action_id"] == "wake-action:cancel-1"
    assert inspection["operator_actions"][0]["command_class"] == "release_or_revoke_lease"


def _run_record() -> RunRecord:
    return RunRecord(
        run_id="run-1",
        workload_id="governed-report",
        workload_version="governed_agent_loop.v1",
        policy_snapshot_id="policy:1",
        policy_digest="sha256:" + "p" * 64,
        configuration_snapshot_id="config:1",
        configuration_digest="sha256:" + "c" * 64,
        creation_timestamp="2026-09-07T12:00:00Z",
        admission_decision_receipt_ref="admission:1",
        lifecycle_state=RunState.CREATED,
    )
