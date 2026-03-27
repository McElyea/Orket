# Layer: integration

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_workload_catalog import (
    GITEA_STATE_WORKER_EXECUTION_WORKLOAD,
)
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.gitea_state_control_plane_checkpoint_service import (
    GiteaStateControlPlaneCheckpointService,
)
from orket.application.services.gitea_state_control_plane_execution_service import (
    GiteaStateControlPlaneExecutionService,
)
from orket.application.services.gitea_state_control_plane_lease_service import (
    GiteaStateControlPlaneLeaseService,
)
from orket.application.services.gitea_state_control_plane_reservation_service import (
    GiteaStateControlPlaneReservationService,
)
from orket.application.services.gitea_state_worker import GiteaStateWorker
from orket.core.domain import (
    AttemptState,
    CheckpointAcceptanceOutcome,
    CheckpointResumabilityClass,
    CleanupAuthorityClass,
    ClosureBasisClassification,
    DivergenceClass,
    ExecutionFailureClass,
    FailurePlane,
    LeaseStatus,
    OrphanClassification,
    OwnershipClass,
    RecoveryActionClass,
    ResourceFailureClass,
    ReservationStatus,
    ResultClass,
    RunState,
)


pytestmark = pytest.mark.integration


class _FakeAdapter:
    def __init__(self) -> None:
        self.cards = [{"issue_number": 7, "state": "ready"}]
        self.calls: list[tuple] = []
        self.acquire_result: dict[str, object] | None = None
        self.renew_results: list[dict[str, object]] = []
        self.transition_error: Exception | None = None

    async def fetch_ready_cards(self, *, limit: int = 1):
        self.calls.append(("fetch_ready_cards", limit))
        return list(self.cards)

    async def acquire_lease(self, card_id: str, *, owner_id: str, lease_seconds: int):
        self.calls.append(("acquire_lease", card_id, owner_id, lease_seconds))
        return self.acquire_result

    async def transition_state(self, card_id: str, *, from_state: str, to_state: str, reason: str | None = None):
        self.calls.append(("transition_state", card_id, from_state, to_state, reason))
        if self.transition_error is not None:
            raise self.transition_error

    async def renew_lease(self, card_id: str, *, owner_id: str, lease_seconds: int, expected_lease_epoch=None):
        self.calls.append(("renew_lease", card_id, owner_id, lease_seconds, expected_lease_epoch))
        if self.renew_results:
            return self.renew_results.pop(0)
        return {"ok": True}

    async def release_or_fail(self, card_id: str, *, final_state: str, error: str | None = None):
        self.calls.append(("release_or_fail", card_id, final_state, error))


def _lease_response(*, card_id: str, worker_id: str, epoch: int, version: int, expires_at: str) -> dict[str, object]:
    return {
        "card_id": f"ISSUE-{card_id}",
        "issue_number": int(card_id),
        "lease": {
            "owner_id": worker_id,
            "acquired_at": "2026-03-24T01:00:00+00:00",
            "expires_at": expires_at,
            "epoch": epoch,
        },
        "version": version,
    }


@pytest.mark.asyncio
async def test_gitea_state_worker_publishes_non_sandbox_lease_history_on_success(tmp_path: Path) -> None:
    execution_repository = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    control_plane_execution = GiteaStateControlPlaneExecutionService(
        execution_repository=execution_repository,
        publication=publication,
    )
    control_plane_checkpoint = GiteaStateControlPlaneCheckpointService(publication=publication)
    control_plane_reservation = GiteaStateControlPlaneReservationService(publication=publication)
    adapter = _FakeAdapter()
    adapter.acquire_result = _lease_response(
        card_id="7",
        worker_id="worker-a",
        epoch=1,
        version=4,
        expires_at="2026-03-24T01:00:30+00:00",
    )
    adapter.renew_results = [
        _lease_response(
            card_id="7",
            worker_id="worker-a",
            epoch=1,
            version=5,
            expires_at="2026-03-24T01:01:00+00:00",
        )
    ]
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-a",
        lease_seconds=1,
        renew_interval_seconds=0.05,
        control_plane_checkpoint_service=control_plane_checkpoint,
        control_plane_execution_service=control_plane_execution,
        control_plane_lease_service=control_plane,
        control_plane_reservation_service=control_plane_reservation,
    )

    async def _work(_card):
        await asyncio.sleep(0.12)
        return {"ok": True}

    consumed = await worker.run_once(work_fn=_work)
    history = await repository.list_lease_records(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("7")
    )
    latest = await repository.get_latest_lease_record(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("7")
    )
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("7")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("7")
    )
    run_id = GiteaStateControlPlaneExecutionService.run_id_for(card_id="7", lease_epoch=1)
    attempt_id = GiteaStateControlPlaneExecutionService.attempt_id_for(run_id=run_id)
    run = await execution_repository.get_run_record(run_id=run_id)
    attempt = await execution_repository.get_attempt_record(attempt_id=attempt_id)
    policy_snapshot = None if run is None else await repository.get_resolved_policy_snapshot(
        snapshot_id=run.policy_snapshot_id
    )
    configuration_snapshot = None if run is None else await repository.get_resolved_configuration_snapshot(
        snapshot_id=run.configuration_snapshot_id
    )
    steps = await execution_repository.list_step_records(attempt_id=attempt_id)
    effects = await repository.list_effect_journal_entries(run_id=run_id)
    checkpoint = await repository.get_checkpoint(checkpoint_id=f"gitea-state-checkpoint:{attempt_id}")
    checkpoint_acceptance = None if checkpoint is None else await repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoint.checkpoint_id
    )
    truth = await repository.get_final_truth(run_id=run_id)
    reservation_history = await repository.list_reservation_records(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("7", 1)
    )

    assert consumed is True
    assert latest is not None
    assert latest_resource is not None
    assert run is not None
    assert attempt is not None
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert checkpoint is not None
    assert checkpoint_acceptance is not None
    assert truth is not None
    assert history[0].status is LeaseStatus.ACTIVE
    assert history[-1].status is LeaseStatus.RELEASED
    assert any(record.status is LeaseStatus.ACTIVE and record.last_confirmed_observation.endswith("version:5") for record in history)
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]
    assert latest.resource_id == "gitea-card:7"
    assert latest.holder_ref == "gitea-worker:worker-a"
    assert latest_resource.resource_kind == "gitea_card"
    assert latest_resource.orphan_classification is OrphanClassification.NOT_ORPHANED
    assert run.lifecycle_state is RunState.COMPLETED
    assert run.workload_id == GITEA_STATE_WORKER_EXECUTION_WORKLOAD.workload_id
    assert run.workload_version == GITEA_STATE_WORKER_EXECUTION_WORKLOAD.workload_version
    assert run.namespace_scope == "issue:7"
    assert attempt.attempt_state is AttemptState.COMPLETED
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_FORBIDDEN
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert len(steps) == 2
    assert len(effects) == 2
    assert truth.result_class is ResultClass.SUCCESS
    assert truth.authoritative_result_ref == steps[-1].output_ref
    assert history[0].source_reservation_id == "gitea-claim-reservation:7:lease_epoch:00000001"
    assert policy_snapshot.snapshot_digest == run.policy_digest
    assert configuration_snapshot.snapshot_digest == run.configuration_digest


@pytest.mark.asyncio
async def test_gitea_state_worker_publishes_expired_non_sandbox_lease_on_epoch_mismatch(tmp_path: Path) -> None:
    execution_repository = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    control_plane_execution = GiteaStateControlPlaneExecutionService(
        execution_repository=execution_repository,
        publication=publication,
    )
    control_plane_checkpoint = GiteaStateControlPlaneCheckpointService(publication=publication)
    control_plane_reservation = GiteaStateControlPlaneReservationService(publication=publication)
    adapter = _FakeAdapter()
    adapter.acquire_result = _lease_response(
        card_id="7",
        worker_id="worker-a",
        epoch=7,
        version=4,
        expires_at="2026-03-24T01:00:30+00:00",
    )
    adapter.renew_results = [
        _lease_response(
            card_id="7",
            worker_id="worker-a",
            epoch=8,
            version=5,
            expires_at="2026-03-24T01:01:00+00:00",
        )
    ]
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-a",
        lease_seconds=1,
        renew_interval_seconds=0.05,
        control_plane_checkpoint_service=control_plane_checkpoint,
        control_plane_execution_service=control_plane_execution,
        control_plane_lease_service=control_plane,
        control_plane_reservation_service=control_plane_reservation,
    )

    async def _work(_card):
        await asyncio.sleep(0.12)
        return {"ok": True}

    consumed = await worker.run_once(work_fn=_work)
    history = await repository.list_lease_records(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("7")
    )
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("7")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("7")
    )
    run_id = GiteaStateControlPlaneExecutionService.run_id_for(card_id="7", lease_epoch=7)
    attempt_id = GiteaStateControlPlaneExecutionService.attempt_id_for(run_id=run_id)
    run = await execution_repository.get_run_record(run_id=run_id)
    attempt = await execution_repository.get_attempt_record(attempt_id=attempt_id)
    steps = await execution_repository.list_step_records(attempt_id=attempt_id)
    effects = await repository.list_effect_journal_entries(run_id=run_id)
    checkpoint = await repository.get_checkpoint(checkpoint_id=f"gitea-state-checkpoint:{attempt_id}")
    checkpoint_acceptance = None if checkpoint is None else await repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoint.checkpoint_id
    )
    truth = await repository.get_final_truth(run_id=run_id)
    decision = None if attempt is None or attempt.recovery_decision_id is None else await repository.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )
    reservation_history = await repository.list_reservation_records(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("7", 7)
    )

    assert consumed is True
    assert run is not None
    assert attempt is not None
    assert latest_resource is not None
    assert checkpoint is not None
    assert checkpoint_acceptance is not None
    assert truth is not None
    assert decision is not None
    assert [record.status for record in history] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.EXPIRED,
    ]
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_expired",
    ]
    assert latest_resource.orphan_classification is OrphanClassification.NOT_ORPHANED
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.INTERRUPTED
    assert attempt.failure_plane is FailurePlane.RESOURCE
    assert attempt.failure_classification is ResourceFailureClass.RESOURCE_UNAVAILABLE
    assert attempt.recovery_decision_id == decision.decision_id
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_FORBIDDEN
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert len(steps) == 2
    assert len(effects) == 2
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.failure_classification_basis == "lease_expired"
    assert decision.failure_plane is FailurePlane.RESOURCE
    assert decision.failure_classification is ResourceFailureClass.RESOURCE_UNAVAILABLE
    assert truth.result_class is ResultClass.BLOCKED
    assert ("release_or_fail", "7", "blocked", "E_LEASE_EXPIRED") in adapter.calls


@pytest.mark.asyncio
async def test_gitea_state_worker_publishes_terminal_recovery_decision_on_runtime_failure(tmp_path: Path) -> None:
    execution_repository = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    control_plane_execution = GiteaStateControlPlaneExecutionService(
        execution_repository=execution_repository,
        publication=publication,
    )
    control_plane_checkpoint = GiteaStateControlPlaneCheckpointService(publication=publication)
    control_plane_reservation = GiteaStateControlPlaneReservationService(publication=publication)
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 9, "state": "ready"}]
    adapter.acquire_result = _lease_response(
        card_id="9",
        worker_id="worker-b",
        epoch=3,
        version=4,
        expires_at="2026-03-24T01:00:30+00:00",
    )
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-b",
        lease_seconds=1,
        renew_interval_seconds=0.05,
        control_plane_checkpoint_service=control_plane_checkpoint,
        control_plane_execution_service=control_plane_execution,
        control_plane_lease_service=control_plane,
        control_plane_reservation_service=control_plane_reservation,
    )

    async def _work(_card):
        raise RuntimeError("boom")

    consumed = await worker.run_once(work_fn=_work)
    run_id = GiteaStateControlPlaneExecutionService.run_id_for(card_id="9", lease_epoch=3)
    attempt_id = GiteaStateControlPlaneExecutionService.attempt_id_for(run_id=run_id)
    run = await execution_repository.get_run_record(run_id=run_id)
    attempt = await execution_repository.get_attempt_record(attempt_id=attempt_id)
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("9")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("9")
    )
    truth = await repository.get_final_truth(run_id=run_id)
    decision = None if attempt is None or attempt.recovery_decision_id is None else await repository.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )
    reservation_history = await repository.list_reservation_records(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("9", 3)
    )

    assert consumed is True
    assert run is not None
    assert attempt is not None
    assert latest_resource is not None
    assert truth is not None
    assert decision is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.failure_class == "gitea_state_worker_failure"
    assert attempt.failure_plane is FailurePlane.EXECUTION
    assert attempt.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]
    assert latest_resource.orphan_classification is OrphanClassification.NOT_ORPHANED
    assert attempt.recovery_decision_id == decision.decision_id
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.failure_classification_basis == "gitea_state_worker_failure"
    assert decision.failure_plane is FailurePlane.EXECUTION
    assert decision.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert truth.result_class is ResultClass.FAILED
    assert ("release_or_fail", "9", "blocked", "boom") in adapter.calls


@pytest.mark.asyncio
async def test_gitea_state_worker_closes_pre_effect_claim_failure_without_fake_release(tmp_path: Path) -> None:
    execution_repository = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    control_plane_execution = GiteaStateControlPlaneExecutionService(
        execution_repository=execution_repository,
        publication=publication,
    )
    control_plane_checkpoint = GiteaStateControlPlaneCheckpointService(publication=publication)
    control_plane_reservation = GiteaStateControlPlaneReservationService(publication=publication)
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 11, "state": "ready"}]
    adapter.acquire_result = _lease_response(
        card_id="11",
        worker_id="worker-c",
        epoch=2,
        version=6,
        expires_at="2026-03-24T01:00:30+00:00",
    )
    adapter.transition_error = ValueError("Stale transition rejected for 11: compare-and-swap conflict.")
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-c",
        lease_seconds=1,
        renew_interval_seconds=0.05,
        control_plane_checkpoint_service=control_plane_checkpoint,
        control_plane_execution_service=control_plane_execution,
        control_plane_lease_service=control_plane,
        control_plane_reservation_service=control_plane_reservation,
    )

    async def _work(_card):
        raise AssertionError("work_fn should not run after claim-transition failure")

    consumed = await worker.run_once(work_fn=_work)
    run_id = GiteaStateControlPlaneExecutionService.run_id_for(card_id="11", lease_epoch=2)
    attempt_id = GiteaStateControlPlaneExecutionService.attempt_id_for(run_id=run_id)
    run = await execution_repository.get_run_record(run_id=run_id)
    attempt = await execution_repository.get_attempt_record(attempt_id=attempt_id)
    steps = await execution_repository.list_step_records(attempt_id=attempt_id)
    effects = await repository.list_effect_journal_entries(run_id=run_id)
    checkpoint = await repository.get_checkpoint(checkpoint_id=f"gitea-state-checkpoint:{attempt_id}")
    checkpoint_acceptance = None if checkpoint is None else await repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoint.checkpoint_id
    )
    latest_lease = await repository.get_latest_lease_record(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("11")
    )
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("11")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("11")
    )
    truth = await repository.get_final_truth(run_id=run_id)
    reconciliation = await repository.get_reconciliation_record(
        reconciliation_id=f"gitea-state-reconciliation:{run_id}:claim_failure"
    )
    decision = None if attempt is None or attempt.recovery_decision_id is None else await repository.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )
    reservation_history = await repository.list_reservation_records(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("11", 2)
    )

    assert consumed is True
    assert run is not None
    assert attempt is not None
    assert checkpoint is not None
    assert checkpoint_acceptance is not None
    assert latest_lease is not None
    assert latest_resource is not None
    assert truth is not None
    assert reconciliation is not None
    assert decision is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.failure_class == "gitea_state_claim_failure"
    assert attempt.failure_plane is FailurePlane.EXECUTION
    assert attempt.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_FORBIDDEN
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert latest_lease.status is LeaseStatus.UNCERTAIN
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_uncertain",
    ]
    assert latest_resource.orphan_classification is OrphanClassification.OWNERSHIP_CONFLICT
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.INVALIDATED,
    ]
    assert len(steps) == 1
    assert steps[0].closure_classification == "step_failed"
    assert steps[0].observed_result_classification == "state_transition_failed"
    assert effects == []
    assert reconciliation.divergence_class is DivergenceClass.INSUFFICIENT_OBSERVATION
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.failure_classification_basis == "gitea_state_claim_failure"
    assert decision.failure_plane is FailurePlane.EXECUTION
    assert decision.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
    assert truth.authoritative_result_ref == steps[0].output_ref
    assert ("release_or_fail", "11", "blocked", "Stale transition rejected for 11: compare-and-swap conflict.") not in adapter.calls


@pytest.mark.asyncio
async def test_gitea_state_worker_closes_claim_stage_runtime_error_then_reraises(tmp_path: Path) -> None:
    execution_repository = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    control_plane_execution = GiteaStateControlPlaneExecutionService(
        execution_repository=execution_repository,
        publication=publication,
    )
    control_plane_checkpoint = GiteaStateControlPlaneCheckpointService(publication=publication)
    control_plane_reservation = GiteaStateControlPlaneReservationService(publication=publication)
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 12, "state": "ready"}]
    adapter.acquire_result = _lease_response(
        card_id="12",
        worker_id="worker-d",
        epoch=4,
        version=8,
        expires_at="2026-03-24T01:00:30+00:00",
    )
    adapter.transition_error = RuntimeError("gitea backend unavailable")
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-d",
        lease_seconds=1,
        renew_interval_seconds=0.05,
        control_plane_checkpoint_service=control_plane_checkpoint,
        control_plane_execution_service=control_plane_execution,
        control_plane_lease_service=control_plane,
        control_plane_reservation_service=control_plane_reservation,
    )

    async def _work(_card):
        raise AssertionError("work_fn should not run after claim-stage runtime failure")

    with pytest.raises(RuntimeError, match="gitea backend unavailable"):
        await worker.run_once(work_fn=_work)

    run_id = GiteaStateControlPlaneExecutionService.run_id_for(card_id="12", lease_epoch=4)
    attempt_id = GiteaStateControlPlaneExecutionService.attempt_id_for(run_id=run_id)
    run = await execution_repository.get_run_record(run_id=run_id)
    attempt = await execution_repository.get_attempt_record(attempt_id=attempt_id)
    steps = await execution_repository.list_step_records(attempt_id=attempt_id)
    effects = await repository.list_effect_journal_entries(run_id=run_id)
    latest_lease = await repository.get_latest_lease_record(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("12")
    )
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("12")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("12")
    )
    truth = await repository.get_final_truth(run_id=run_id)
    reconciliation = await repository.get_reconciliation_record(
        reconciliation_id=f"gitea-state-reconciliation:{run_id}:claim_failure"
    )
    decision = None if attempt is None or attempt.recovery_decision_id is None else await repository.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )
    reservation_history = await repository.list_reservation_records(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("12", 4)
    )

    assert run is not None
    assert attempt is not None
    assert latest_lease is not None
    assert latest_resource is not None
    assert truth is not None
    assert reconciliation is not None
    assert decision is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.failure_plane is FailurePlane.EXECUTION
    assert attempt.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert latest_lease.status is LeaseStatus.UNCERTAIN
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_uncertain",
    ]
    assert latest_resource.orphan_classification is OrphanClassification.OWNERSHIP_CONFLICT
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.INVALIDATED,
    ]
    assert len(steps) == 1
    assert effects == []
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
    assert decision.failure_plane is FailurePlane.EXECUTION
    assert decision.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert ("release_or_fail", "12", "blocked", "gitea backend unavailable") not in adapter.calls


@pytest.mark.asyncio
async def test_gitea_state_worker_fail_closes_authority_on_claim_promotion_failure(tmp_path: Path) -> None:
    execution_repository = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    control_plane_execution = GiteaStateControlPlaneExecutionService(
        execution_repository=execution_repository,
        publication=publication,
    )
    control_plane_checkpoint = GiteaStateControlPlaneCheckpointService(publication=publication)
    control_plane_reservation = GiteaStateControlPlaneReservationService(publication=publication)
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 13, "state": "ready"}]
    adapter.acquire_result = _lease_response(
        card_id="13",
        worker_id="worker-z",
        epoch=5,
        version=3,
        expires_at="2026-03-24T01:00:30+00:00",
    )
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-z",
        lease_seconds=1,
        renew_interval_seconds=0.05,
        control_plane_checkpoint_service=control_plane_checkpoint,
        control_plane_execution_service=control_plane_execution,
        control_plane_lease_service=control_plane,
        control_plane_reservation_service=control_plane_reservation,
    )

    async def _raise_promote_failure(**_kwargs):
        raise RuntimeError("promote failed")

    publication.promote_reservation_to_lease = _raise_promote_failure  # type: ignore[method-assign]

    async def _work(_card):
        raise AssertionError("work_fn should not run after claim-promotion failure")

    with pytest.raises(RuntimeError, match="promote failed"):
        await worker.run_once(work_fn=_work)

    reservation_history = await repository.list_reservation_records(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("13", 5)
    )
    lease_history = await repository.list_lease_records(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("13")
    )
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("13")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("13")
    )

    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.INVALIDATED,
    ]
    assert (
        reservation_history[-1].expiry_or_invalidation_basis
        == "gitea_state_worker_claim_promotion_failed;lease_epoch=00000005"
    )
    assert [record.status for record in lease_history] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
    ]
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]
    assert latest_resource is not None
    assert latest_resource.orphan_classification is OrphanClassification.NOT_ORPHANED
    assert lease_history[-1].expiry_basis == "gitea_state_worker_claim_promotion_failed;lease_epoch=00000005"
    assert ("release_or_fail", "13", "blocked", "promote failed") not in adapter.calls


@pytest.mark.asyncio
async def test_gitea_state_worker_republishes_released_lease_when_resource_truth_drifted(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    worker = GiteaStateWorker(
        adapter=_FakeAdapter(),
        worker_id="worker-heal-release",
        control_plane_lease_service=control_plane,
    )
    lease_observation = _lease_response(
        card_id="21",
        worker_id="worker-heal-release",
        epoch=2,
        version=4,
        expires_at="2026-03-24T01:00:30+00:00",
    )

    await control_plane.publish_claimed_lease(
        card_id="21",
        worker_id="worker-heal-release",
        lease_observation=lease_observation,
        lease_seconds=30,
    )
    await control_plane.publish_released_lease(
        card_id="21",
        worker_id="worker-heal-release",
        lease_observation=lease_observation,
        final_state="code_review",
    )
    await publication.publish_resource(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("21"),
        resource_kind="gitea_card",
        namespace_scope="issue:21",
        ownership_class=OwnershipClass.SHARED_GOVERNED,
        current_observed_state="lease_status:lease_active;observation:drifted",
        last_observed_timestamp="2026-03-24T01:02:00+00:00",
        cleanup_authority_class=CleanupAuthorityClass.CLEANUP_FORBIDDEN_WITHOUT_EXTERNAL_CONFIRMATION,
        provenance_ref="gitea-card-snapshot:21:version:999",
        reconciliation_status="external_state_authoritative",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )

    await worker._publish_released_lease_if_enabled(
        card_id="21",
        lease_observation=lease_observation,
        final_state="code_review",
    )

    lease_history = await repository.list_lease_records(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("21")
    )
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("21")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("21")
    )

    assert [record.status for record in lease_history] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
        LeaseStatus.RELEASED,
    ]
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]
    assert latest_resource is not None
    assert latest_resource.current_observed_state.startswith("lease_status:lease_released;")


@pytest.mark.asyncio
async def test_gitea_state_worker_republishes_expired_lease_when_resource_truth_drifted(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    worker = GiteaStateWorker(
        adapter=_FakeAdapter(),
        worker_id="worker-heal-expiry",
        control_plane_lease_service=control_plane,
    )
    lease_observation = _lease_response(
        card_id="22",
        worker_id="worker-heal-expiry",
        epoch=3,
        version=5,
        expires_at="2026-03-24T01:00:30+00:00",
    )

    await control_plane.publish_claimed_lease(
        card_id="22",
        worker_id="worker-heal-expiry",
        lease_observation=lease_observation,
        lease_seconds=30,
    )
    await control_plane.publish_expired_lease(
        card_id="22",
        worker_id="worker-heal-expiry",
        lease_observation=lease_observation,
        reason="E_LEASE_EXPIRED",
    )
    await publication.publish_resource(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("22"),
        resource_kind="gitea_card",
        namespace_scope="issue:22",
        ownership_class=OwnershipClass.SHARED_GOVERNED,
        current_observed_state="lease_status:lease_active;observation:drifted",
        last_observed_timestamp="2026-03-24T01:02:00+00:00",
        cleanup_authority_class=CleanupAuthorityClass.CLEANUP_FORBIDDEN_WITHOUT_EXTERNAL_CONFIRMATION,
        provenance_ref="gitea-card-snapshot:22:version:999",
        reconciliation_status="external_state_authoritative",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )

    await worker._publish_expired_lease_if_enabled(
        card_id="22",
        lease_observation=lease_observation,
        reason="E_LEASE_EXPIRED",
    )

    lease_history = await repository.list_lease_records(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("22")
    )
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("22")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("22")
    )

    assert [record.status for record in lease_history] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.EXPIRED,
        LeaseStatus.EXPIRED,
    ]
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_expired",
        "lease_status:lease_active",
        "lease_status:lease_expired",
    ]
    assert latest_resource is not None
    assert latest_resource.current_observed_state.startswith("lease_status:lease_expired;")


@pytest.mark.asyncio
async def test_gitea_state_worker_blocks_before_backend_renew_on_active_resource_drift(tmp_path: Path) -> None:
    execution_repository = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    publication = ControlPlanePublicationService(repository=repository)
    control_plane = GiteaStateControlPlaneLeaseService(publication=publication)
    control_plane_execution = GiteaStateControlPlaneExecutionService(
        execution_repository=execution_repository,
        publication=publication,
    )
    control_plane_checkpoint = GiteaStateControlPlaneCheckpointService(publication=publication)
    control_plane_reservation = GiteaStateControlPlaneReservationService(publication=publication)
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 23, "state": "ready"}]
    adapter.acquire_result = _lease_response(
        card_id="23",
        worker_id="worker-renew-drift",
        epoch=6,
        version=4,
        expires_at="2026-03-24T01:00:30+00:00",
    )
    adapter.renew_results = [
        _lease_response(
            card_id="23",
            worker_id="worker-renew-drift",
            epoch=6,
            version=5,
            expires_at="2026-03-24T01:01:00+00:00",
        )
    ]
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-renew-drift",
        lease_seconds=1,
        renew_interval_seconds=0.05,
        control_plane_checkpoint_service=control_plane_checkpoint,
        control_plane_execution_service=control_plane_execution,
        control_plane_lease_service=control_plane,
        control_plane_reservation_service=control_plane_reservation,
    )

    async def _work(_card):
        await asyncio.sleep(0.02)
        await publication.publish_resource(
            resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("23"),
            resource_kind="gitea_card",
            namespace_scope=GiteaStateControlPlaneLeaseService.namespace_scope_for("23"),
            ownership_class=OwnershipClass.SHARED_GOVERNED,
            current_observed_state="lease_status:lease_released;observation:drifted",
            last_observed_timestamp="2026-03-24T01:00:10+00:00",
            cleanup_authority_class=CleanupAuthorityClass.CLEANUP_FORBIDDEN_WITHOUT_EXTERNAL_CONFIRMATION,
            provenance_ref="gitea-card-snapshot:23:version:999",
            reconciliation_status="external_state_authoritative",
            orphan_classification=OrphanClassification.NOT_ORPHANED,
        )
        await asyncio.sleep(0.12)
        return {"ok": True}

    consumed = await worker.run_once(work_fn=_work)
    run_id = GiteaStateControlPlaneExecutionService.run_id_for(card_id="23", lease_epoch=6)
    attempt_id = GiteaStateControlPlaneExecutionService.attempt_id_for(run_id=run_id)
    run = await execution_repository.get_run_record(run_id=run_id)
    attempt = await execution_repository.get_attempt_record(attempt_id=attempt_id)
    truth = await repository.get_final_truth(run_id=run_id)
    decision = None if attempt is None or attempt.recovery_decision_id is None else await repository.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )
    lease_history = await repository.list_lease_records(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("23")
    )
    resource_history = await repository.list_resource_records(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("23")
    )
    latest_resource = await repository.get_latest_resource_record(
        resource_id=GiteaStateControlPlaneLeaseService.resource_id_for("23")
    )

    assert consumed is True
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert decision is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.INTERRUPTED
    assert attempt.failure_class == "control_plane_resource_drift"
    assert attempt.failure_plane is FailurePlane.RESOURCE
    assert attempt.failure_classification is ResourceFailureClass.RESOURCE_STATE_UNCERTAIN
    assert decision.failure_classification_basis == "control_plane_resource_drift"
    assert decision.failure_plane is FailurePlane.RESOURCE
    assert decision.failure_classification is ResourceFailureClass.RESOURCE_STATE_UNCERTAIN
    assert truth.result_class is ResultClass.BLOCKED
    assert [record.status for record in lease_history] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
    ]
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
        "lease_status:lease_released",
    ]
    assert latest_resource is not None
    assert latest_resource.current_observed_state.startswith("lease_status:lease_released;")
    assert not any(call[0] == "renew_lease" for call in adapter.calls)
    assert ("release_or_fail", "23", "blocked", "E_CONTROL_PLANE_RESOURCE_DRIFT") in adapter.calls
