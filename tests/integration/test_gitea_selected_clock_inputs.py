"""Real SQLite clock records with a controlled remote claim failure."""
import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.gitea_state_control_plane_checkpoint_service import (
    GiteaStateControlPlaneCheckpointService,
)
from orket.application.services.gitea_state_control_plane_execution_service import (
    build_gitea_state_control_plane_execution_service,
)
from orket.application.services.gitea_state_control_plane_lease_service import GiteaStateControlPlaneLeaseService
from orket.application.services.gitea_state_control_plane_reservation_service import (
    GiteaStateControlPlaneReservationService,
    build_gitea_state_control_plane_reservation_service,
)
from orket.application.services.gitea_state_worker import GiteaStateWorker
from orket.core.domain import LeaseStatus
from orket.core.domain.control_plane_leases import ControlPlaneLeaseError
from tests.helpers.gitea_control_plane_clock import ordered_utc_clock
from tests.helpers.remaining_family_authority import records
from tests.integration.test_gitea_state_worker_control_plane import _FakeAdapter, _lease_response
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_claim_failure_closeout_uses_selected_execution_clock(tmp_path):
    clock, observations = ordered_utc_clock(), []

    def selected_clock():
        value = clock()
        observations.append(value)
        return value

    database = tmp_path / 'control_plane.sqlite3'
    repository = AsyncControlPlaneRecordRepository(database)
    publication = ControlPlanePublicationService(repository=repository)
    execution = build_gitea_state_control_plane_execution_service(database, now_utc=selected_clock)
    adapter = _FakeAdapter()
    adapter.cards = [{'issue_number': 11, 'state': 'ready'}]
    adapter.acquire_result = _lease_response(card_id='11', worker_id='clock-worker', epoch=2, version=6,
        expires_at='2026-03-24T01:00:30+00:00')
    adapter.transition_error = ValueError('controlled claim conflict')
    worker = GiteaStateWorker(adapter=adapter, worker_id='clock-worker',
        control_plane_execution_service=execution,
        control_plane_lease_service=GiteaStateControlPlaneLeaseService(publication=publication, now_utc=selected_clock),
        control_plane_checkpoint_service=GiteaStateControlPlaneCheckpointService(publication=publication))

    async def forbidden_work(_card):
        raise AssertionError('A failed remote claim must not run the workload')

    assert await worker.run_once(work_fn=forbidden_work)
    rows = await records(database)
    assert rows['final_truth_records'][0]['result_class'] == 'blocked'
    attempt, = rows['control_plane_attempts']
    assert attempt['end_timestamp'] in observations, (attempt['end_timestamp'], observations)
    run_id = rows['control_plane_runs'][0]['run_id']
    reconciliation = await repository.get_reconciliation_record(
        reconciliation_id=f'gitea-state-reconciliation:{run_id}:claim_failure')
    assert reconciliation.publication_timestamp in observations


async def test_promotion_rollback_does_not_clamp_a_reversed_clock(tmp_path, monkeypatch):
    database = tmp_path / 'control_plane.sqlite3'
    repository = AsyncControlPlaneRecordRepository(database)
    publication = ControlPlanePublicationService(repository=repository)
    reservation = GiteaStateControlPlaneReservationService(publication=publication)
    lease = GiteaStateControlPlaneLeaseService(publication=publication,
        now_utc=lambda: '2026-03-24T12:05:02+00:00')
    reserved = await reservation.publish_claim_reservation(card_id='9', worker_id='clock-worker', lease_epoch=5,
        observed_at='2026-03-24T12:05:00+00:00')
    await lease.publish_claimed_lease(card_id='9', worker_id='clock-worker', lease_seconds=30,
        source_reservation_id=reserved.reservation_id,
        lease_observation=_lease_response(card_id='9', worker_id='clock-worker', epoch=5, version=9,
            expires_at='2026-03-24T12:06:00+00:00'))
    before = await logical_state(database)

    async def failed_promotion(**_values):
        raise RuntimeError('controlled promotion failure')

    monkeypatch.setattr(publication, 'promote_reservation_to_lease', failed_promotion)
    with pytest.raises((RuntimeError, ControlPlaneLeaseError)) as raised:
        await reservation.promote_claim_reservation(card_id='9', lease_epoch=5,
            observed_at='2026-03-24T12:05:01+00:00')
    retained = await repository.get_latest_lease_record(lease_id='gitea-card-lease:9')
    assert isinstance(raised.value, ControlPlaneLeaseError) and retained.status is LeaseStatus.ACTIVE, (
        type(raised.value).__name__, retained.status, retained.publication_timestamp)
    assert 'monotonically' in str(raised.value)
    assert isinstance(raised.value.__context__, RuntimeError)
    assert await logical_state(database) == before


@pytest.mark.parametrize('explicit', [False, True])
async def test_reservation_clock_and_explicit_observation_persist(tmp_path, explicit):
    observations = []
    ticks = iter(['2026-03-24T12:00:00+00:00', '2026-03-24T12:00:01+00:00'])

    def selected_clock():
        assert not explicit, 'An explicit observation must not read the clock'
        value = next(ticks)
        observations.append(value)
        return value

    owner = build_gitea_state_control_plane_reservation_service(tmp_path / 'records.sqlite3', now_utc=selected_clock)
    creation, promotion = '2026-03-24T12:00:00+00:00', '2026-03-24T12:00:01+00:00'
    await owner.publish_claim_reservation(card_id='17', worker_id='selected-worker', lease_epoch=1,
        observed_at=creation if explicit else None)
    await owner.promote_claim_reservation(card_id='17', lease_epoch=1, observed_at=promotion if explicit else None)
    retained = await owner.publication.repository.get_latest_reservation_record(reservation_id=owner.reservation_id_for('17', 1))
    assert retained.creation_timestamp == creation and retained.status.value == 'reservation_promoted_to_lease'
    assert promotion in retained.expiry_or_invalidation_basis
    assert observations == ([] if explicit else [creation, promotion])


@pytest.mark.parametrize('stage', ['create', 'promote'])
async def test_reservation_clock_failure_precedes_publication(tmp_path, stage):
    def unavailable():
        raise OSError('selected-reservation-clock-unavailable')

    database = tmp_path / 'records.sqlite3'
    owner = build_gitea_state_control_plane_reservation_service(database, now_utc=unavailable)
    # Seed an independent record so the exact retained SQLite state can be compared.
    await owner.publish_claim_reservation(card_id='17', worker_id='selected-worker', lease_epoch=1,
        observed_at='2026-03-24T12:00:00+00:00')
    before = await logical_state(database)
    with pytest.raises(OSError, match='selected-reservation-clock-unavailable'):
        if stage == 'create':
            await owner.publish_claim_reservation(card_id='18', worker_id='selected-worker', lease_epoch=1)
        else:
            await owner.promote_claim_reservation(card_id='17', lease_epoch=1)
    assert await logical_state(database) == before
