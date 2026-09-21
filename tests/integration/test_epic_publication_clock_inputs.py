"""Layer: integration. Publication preserves the ledger's timestamp admission rule."""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.application.test_execution_pipeline_protocol_run_ledger import _write_epic_assets
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
@pytest.mark.parametrize('rewind', [False, True])
async def test_protocol_publication_accepts_ordered_time_and_preserves_clock_refusal(
    test_root, workspace, db_path, monkeypatch, rewind,
):
    await asyncio.to_thread(_write_epic_assets, test_root, 'clock_epic')
    clock = ProtocolLedgerClock()
    ledger = AsyncProtocolRunLedgerRepository(workspace, timestamp_factory=clock.utc_now_iso)
    async with ExecutionPipeline.open(workspace=workspace, department='core', db_path=db_path,
                                 config_root=test_root, run_ledger_repo=ledger, runtime_inputs=clock) as pipeline:

        async def no_work(**kwargs):
            return None

        async def export_boundary(**kwargs):
            if rewind:
                clock.rewind()
            return None

        monkeypatch.setattr(pipeline.orchestrator, 'execute_epic', no_work)
        monkeypatch.setattr(pipeline.artifact_exporter, 'export_run', export_boundary)
        try:
            result = await pipeline.run_epic('clock_epic', build_id='clock-build', session_id='clock-session')
            run = await ledger.get_run('clock-session')
            events = await ledger.list_events('clock-session')
            assert not result.succeeded
            async with pipeline.epic_publication.repository.transaction('clock-session') as transaction:
                publication = await transaction.get()
            final_time = datetime.fromisoformat(publication.plan.ledger['finalized_at'])
            if rewind:
                assert result.observation == 'unresolved' and 'E_LEDGER_TIMESTAMP_NON_MONOTONIC' in result.reason
                assert run['status'] == 'running' and publication.phase == 0
                assert [event['kind'] for event in events] == ['run_started', 'packet2_fact']
                assert final_time < datetime.fromisoformat(events[-1]['timestamp'])
            else:
                assert result.observation == 'published' and run['status'] == 'incomplete'
                assert [event['kind'] for event in events] == ['run_started', 'packet2_fact', 'run_finalized']
                assert final_time >= datetime.fromisoformat(events[-2]['timestamp'])
        finally:
            await pipeline.close()
