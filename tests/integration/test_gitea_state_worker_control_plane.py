# Layer: integration

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
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
    ClosureBasisClassification,
    DivergenceClass,
    LeaseStatus,
    RecoveryActionClass,
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
    run_id = GiteaStateControlPlaneExecutionService.run_id_for(card_id="7", lease_epoch=1)
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
    reservation_history = await repository.list_reservation_records(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("7", 1)
    )

    assert consumed is True
    assert latest is not None
    assert run is not None
    assert attempt is not None
    assert checkpoint is not None
    assert checkpoint_acceptance is not None
    assert truth is not None
    assert history[0].status is LeaseStatus.ACTIVE
    assert history[-1].status is LeaseStatus.RELEASED
    assert any(record.status is LeaseStatus.ACTIVE and record.last_confirmed_observation.endswith("version:5") for record in history)
    assert latest.resource_id == "gitea-card:7"
    assert latest.holder_ref == "gitea-worker:worker-a"
    assert run.lifecycle_state is RunState.COMPLETED
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
    assert checkpoint is not None
    assert checkpoint_acceptance is not None
    assert truth is not None
    assert decision is not None
    assert [record.status for record in history] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.EXPIRED,
    ]
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.INTERRUPTED
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
    assert truth is not None
    assert decision is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.failure_class == "gitea_state_worker_failure"
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert attempt.recovery_decision_id == decision.decision_id
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.failure_classification_basis == "gitea_state_worker_failure"
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
    assert truth is not None
    assert reconciliation is not None
    assert decision is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.failure_class == "gitea_state_claim_failure"
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_FORBIDDEN
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert latest_lease.status is LeaseStatus.UNCERTAIN
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
    truth = await repository.get_final_truth(run_id=run_id)
    reconciliation = await repository.get_reconciliation_record(
        reconciliation_id=f"gitea-state-reconciliation:{run_id}:claim_failure"
    )
    reservation_history = await repository.list_reservation_records(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("12", 4)
    )

    assert run is not None
    assert attempt is not None
    assert latest_lease is not None
    assert truth is not None
    assert reconciliation is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert latest_lease.status is LeaseStatus.UNCERTAIN
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.INVALIDATED,
    ]
    assert len(steps) == 1
    assert effects == []
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
    assert ("release_or_fail", "12", "blocked", "gitea backend unavailable") not in adapter.calls
