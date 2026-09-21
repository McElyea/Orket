"""Explicit issue-clock inputs preserve ordering and refuse the retained reversal."""
from __future__ import annotations

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.orchestrator_issue_control_plane_service import OrchestratorIssueControlPlaneService
from orket.application.services.orchestrator_issue_control_plane_support import run_id_for_dispatch
from orket.core.domain.control_plane_leases import ControlPlaneLeaseError
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock
from tests.integration.test_issue_dispatch_terminal_transaction import dispatch_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ADMITTED = '2026-09-15T02:08:51.880580+00:00'
REVERSED = '2026-09-15T02:08:45.146818+00:00'
ORDERED = '2026-09-15T02:08:52.146818+00:00'


def service_for(path, now):
    return OrchestratorIssueControlPlaneService(
        execution_repository=AsyncControlPlaneExecutionRepository(path),
        publication=ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(path)),
        transactions=SQLiteControlPlaneTransactions(path), now_utc=now,
    )


async def admit(service):
    await service.publish_issue_transition(
        session_id='clock-session', issue_id='clock-issue', current_status='ready',
        target_status='in_progress', reason='turn_dispatch', assignee='coder', turn_index=1,
    )
    return run_id_for_dispatch(session_id='clock-session', issue_id='clock-issue', seat_name='coder', turn_index=1)


# Layer: integration
@pytest.mark.parametrize('reversed_time', [False, True])
async def test_exact_retained_issue_clock_values_preserve_atomic_closeout(tmp_path, reversed_time):
    values = iter([ADMITTED, REVERSED if reversed_time else ORDERED, ORDERED])
    path = tmp_path / 'control-plane.sqlite3'
    service = service_for(path, lambda: next(values))
    run_id = await admit(service)
    before = await dispatch_state(service, run_id)
    assert before[0]['creation_timestamp'] == before[3]['publication_timestamp'] == ADMITTED
    if reversed_time:
        with pytest.raises(ControlPlaneLeaseError, match='timestamps must increase monotonically'):
            await service.close_from_observed_status(
                session_id='clock-session', issue_id='clock-issue', observed_status='done')
        service = service_for(path, lambda: next(values))
        assert await dispatch_state(service, run_id) == before
    await service.close_from_observed_status(session_id='clock-session', issue_id='clock-issue', observed_status='done')
    after = await dispatch_state(service_for(path, lambda: ORDERED), run_id)
    assert after[0]['lifecycle_state'] == 'completed'
    assert after[1]['end_timestamp'] == after[3]['publication_timestamp'] == ORDERED
    assert after[2]['result_class'] == 'success' and after[3]['status'] == 'lease_released'
    effects = await service.publication.repository.list_effect_journal_entries(run_id=run_id)
    assert effects[-1].publication_timestamp == ORDERED


# Layer: integration
async def test_pipeline_issue_dispatch_uses_supplied_runtime_clock(test_root, workspace, db_path):
    clock = ProtocolLedgerClock()
    clock.current = clock.current.replace(year=2041)
    expected = clock.current.isoformat()
    async with ExecutionPipeline.open(workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock) as pipeline:
        try:
            service = pipeline.orchestrator.issue_control_plane
            run_id = await admit(service)
            before = await dispatch_state(service, run_id)
            assert before[0]['creation_timestamp'] == expected
            await service.close_from_observed_status(
                session_id='clock-session', issue_id='clock-issue', observed_status='done')
            after = await dispatch_state(service, run_id)
            assert after[0]['lifecycle_state'] == 'completed'
            assert after[1]['end_timestamp'].startswith('2041-')
        finally:
            await pipeline.close()
