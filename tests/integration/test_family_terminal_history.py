"""The same retained terminal contradictions are refused across admitted families."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.adapters.storage.governed_agent_replay_store import GovernedAgentReplayStore
from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneService
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from orket.core.contracts import RunRecord
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_authorization import outward_api
from tests.integration.test_family_terminal_authority import agent_flow, card_flow, outward_flow, retained_results
from tests.integration.test_governed_agent_terminal_history import damage_terminal_history, logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("elapsed_agent_clock")]


async def observe_family(family, db, run, tmp_path, boundary):
    if family == 'outward':
        async with outward_api(tmp_path, boundary[1]) as (_, context):
            return await context.outward_run_inspection_service.summary(run.run_id)
    if family == 'cards':
        transactions = SQLiteControlPlaneTransactions(db)
        service = CardsEpicControlPlaneService(
            execution_repository=AsyncControlPlaneExecutionRepository(db),
            publication=ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(db)),
            transactions=transactions,
        )
        return await service.finalize_execution(run_id=run.run_id, session_status='done')
    iterations = AsyncGovernedAgentRepository(db)
    inspector = GovernedAgentInspectionService(
        iteration_repository=iterations, call_repository=iterations,
        replay_repository=GovernedAgentReplayStore(db),
    )
    return await inspector.inspect(run_id=run.run_id)


@pytest.mark.parametrize('family', ['outward', 'cards', 'governed_agent'])
@pytest.mark.parametrize('case', ['coherent', 'unreferenced-truth', 'unfinished-attempt', 'multiple-truths'])
# Layer: integration
async def test_family_terminal_projection_refuses_inconsistent_history(
    tmp_path, test_root, workspace, db_path, monkeypatch, boundary, family, case,
):
    if family == 'outward':
        db, _ = await outward_flow(tmp_path, boundary)
    elif family == 'cards':
        db, _ = await card_flow(test_root, workspace, db_path, monkeypatch)
    else:
        db, _ = await agent_flow(tmp_path)
    retained = [row for row in await retained_results(db) if row['truth'] and row['truth']['result_class'] == 'success']
    assert len(retained) == 1
    run = RunRecord.model_validate(retained[0]['run'])
    execution = AsyncControlPlaneExecutionRepository(db)
    transactions = SQLiteControlPlaneTransactions(db)
    async with transactions() as transaction:
        truth = await transaction.records.get_final_truth(run_id=run.run_id)
    result = SimpleNamespace(run=run, attempt=await execution.get_attempt_record(attempt_id=run.current_attempt_id), final_truth=truth)
    await damage_terminal_history(db, result, case)
    before = await logical_state(db)
    if case == 'coherent':
        assert await observe_family(family, db, run, tmp_path, boundary)
    else:
        with pytest.raises((ValueError, RuntimeError), match='CONFLICT'):
            await observe_family(family, db, run, tmp_path, boundary)
    assert await logical_state(db) == before
