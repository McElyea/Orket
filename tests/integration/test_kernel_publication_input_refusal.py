"""Malformed publication input is refused before changing an actual store."""
import json

import aiosqlite
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from tests.integration.test_kernel_publication_input_capture import publication_inputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def database_dump(database):
    async with aiosqlite.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
        return [line async for line in connection.iterdump()]


@pytest.mark.parametrize('operation', ['admission', 'commit', 'session_end'])
@pytest.mark.parametrize('part', ['request', 'response', 'ledger'])
@pytest.mark.parametrize('bad', [float('nan'), object()], ids=['nonfinite', 'unsupported-object'])
async def test_kernel_publication_rejects_invalid_json_before_store_mutation(tmp_path, operation, part, bad):
    database = tmp_path / 'kernel.sqlite3'
    execution = AsyncControlPlaneExecutionRepository(database)
    service = KernelActionControlPlaneService(execution_repository=execution,
        publication=ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(database)))
    await execution.get_run_record(run_id='no-run')
    before = await database_dump(database)
    request, response, ledger = publication_inputs()
    {'request': request, 'response': response, 'ledger': ledger[0]}[part]['extra'] = bad
    with pytest.raises((ValueError, TypeError)):
        await getattr(service, 'record_' + operation)(request=request, response=response, ledger_items=ledger)
    assert await database_dump(database) == before
    assert await execution.get_run_record(run_id='kernel-action-run:session:trace') is None


async def test_detached_capture_preserves_nested_json_and_does_not_mutate_caller(tmp_path):
    database = tmp_path / 'kernel.sqlite3'
    service = KernelActionControlPlaneService(execution_repository=AsyncControlPlaneExecutionRepository(database),
        publication=ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(database)))
    request, response, ledger = publication_inputs()
    before = json.dumps([request, response, ledger], sort_keys=True)
    await service.record_admission(request=request, response=response, ledger_items=ledger)
    assert json.dumps([request, response, ledger], sort_keys=True) == before
