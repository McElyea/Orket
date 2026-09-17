"""Real SQLite mutation preconditions shared by run, attempt and step writers."""
import asyncio
import json

import aiosqlite
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
    ControlPlaneExecutionConflictError,
)
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.domain import AttemptState, RunState

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
KINDS = ['run', 'attempt', 'step']


def initial(kind):
    if kind == 'step':
        return StepRecord(step_id='step', attempt_id='attempt', step_kind='tool', input_ref='input',
                          observed_result_classification='dispatch_started', closure_classification='dispatch_started')
    if kind == 'run':
        return RunRecord(run_id='run', workload_id='workload', workload_version='v1',
            policy_snapshot_id='policy', policy_digest='sha256:policy', configuration_snapshot_id='config',
            configuration_digest='sha256:config', creation_timestamp='2026-09-14T00:00:00+00:00',
            admission_decision_receipt_ref='admission', lifecycle_state=RunState.EXECUTING, current_attempt_id='attempt')
    return AttemptRecord(attempt_id='attempt', run_id='run', attempt_ordinal=1,
        attempt_state=AttemptState.EXECUTING, starting_state_snapshot_ref='start', start_timestamp='2026-09-14T00:00:00+00:00')


async def read(repository, kind):
    if kind == 'run':
        return await repository.get_run_record(run_id='run')
    if kind == 'step':
        return await repository.get_step_record(step_id='step')
    return await repository.get_attempt_record(attempt_id='attempt')


async def save(repository, kind, record):
    if kind == 'run':
        return await repository.save_run_record(record=record)
    if kind == 'step':
        return await repository.save_step_record(record=record)
    return await repository.save_attempt_record(record=record)


def changed(record, kind):
    if kind == 'step':
        return record.model_copy(update={'observed_result_classification': 'tool_succeeded',
                                         'closure_classification': 'step_completed'})
    return record.model_copy(update={'lifecycle_state': RunState.OPERATOR_BLOCKED} if kind == 'run' else {
        'attempt_state': AttemptState.INTERRUPTED, 'end_timestamp': '2026-09-14T00:01:00+00:00'})


@pytest.mark.parametrize('kind', KINDS)
# Layer: integration
async def test_stale_state_cannot_overwrite_newer_state(tmp_path, kind):
    first = AsyncControlPlaneExecutionRepository(tmp_path/'control.sqlite3')
    second = AsyncControlPlaneExecutionRepository(tmp_path/'control.sqlite3')
    original = await save(first, kind, initial(kind))
    observed = await read(second, kind)
    current = await save(first, kind, changed(original, kind))
    with pytest.raises(ControlPlaneExecutionConflictError, match='STATE_CONFLICT'):
        await save(second, kind, observed)
    assert await read(second, kind) == current
    assert original.state_revision == 0 and current.state_revision == 1


@pytest.mark.parametrize('kind', KINDS)
# Layer: integration
async def test_return_to_same_state_does_not_revive_stale_revision(tmp_path, kind):
    repository = AsyncControlPlaneExecutionRepository(tmp_path/'control.sqlite3')
    original = await save(repository, kind, initial(kind))
    middle = await save(repository, kind, changed(original, kind))
    if kind == 'step':
        reverted = middle.model_copy(update={'observed_result_classification': 'dispatch_started',
                                             'closure_classification': 'dispatch_started'})
    else:
        reverted = middle.model_copy(update={'lifecycle_state': RunState.EXECUTING} if kind == 'run' else {
            'attempt_state': AttemptState.EXECUTING, 'end_timestamp': None})
    current = await save(repository, kind, reverted)
    with pytest.raises(ControlPlaneExecutionConflictError, match='STATE_CONFLICT'):
        await save(repository, kind, changed(original, kind))
    assert await read(repository, kind) == current
    assert current.state_revision == 2


@pytest.mark.parametrize('kind', KINDS)
# Layer: integration
async def test_two_observers_admit_only_one_changed_write(tmp_path, kind):
    first = AsyncControlPlaneExecutionRepository(tmp_path/'control.sqlite3')
    second = AsyncControlPlaneExecutionRepository(tmp_path/'control.sqlite3')
    original = await save(first, kind, initial(kind))
    observed = await read(second, kind)
    results = await asyncio.gather(save(first, kind, changed(original, kind)),
                                   save(second, kind, changed(observed, kind)), return_exceptions=True)
    assert sum(isinstance(row, ControlPlaneExecutionConflictError) for row in results) == 1
    assert (await read(first, kind)).state_revision == 1


@pytest.mark.parametrize('kind', KINDS)
# Layer: integration
async def test_creation_requires_absent_identity_and_identical_current_save_is_noop(tmp_path, kind):
    repository = AsyncControlPlaneExecutionRepository(tmp_path/'control.sqlite3')
    proposed = initial(kind)
    current = await save(repository, kind, proposed)
    with pytest.raises(ControlPlaneExecutionConflictError, match='STATE_CONFLICT'):
        await save(repository, kind, proposed)
    assert await save(repository, kind, current) == current
    assert current.state_revision == 0 and proposed.state_revision is None


@pytest.mark.parametrize('kind', KINDS)
# Layer: integration
async def test_legacy_revision_reads_without_backfill_then_changes_once(tmp_path, kind):
    path = tmp_path/'control.sqlite3'
    repository = AsyncControlPlaneExecutionRepository(path)
    current = await save(repository, kind, initial(kind))
    legacy = current.model_dump(mode='json')
    legacy.pop('state_revision', None)
    raw = json.dumps(legacy)
    table = {'run': 'control_plane_runs', 'attempt': 'control_plane_attempts', 'step': 'control_plane_steps'}[kind]
    async with aiosqlite.connect(path) as connection:
        await connection.execute(f'UPDATE {table} SET payload_json=?', (raw,))
        await connection.commit()
    loaded = await read(repository, kind)
    assert loaded.state_revision == 0
    assert await save(repository, kind, loaded) == loaded
    async with aiosqlite.connect(path) as connection:
        cursor = await connection.execute(f'SELECT payload_json FROM {table}')
        assert (await cursor.fetchone())[0] == raw
    updated = await save(repository, kind, changed(loaded, kind))
    assert updated.state_revision == 1
    with pytest.raises(ControlPlaneExecutionConflictError, match='STATE_CONFLICT'):
        await save(repository, kind, loaded)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('cancel', [False, True])
# Layer: integration
async def test_transaction_rollback_preserves_state_and_revision(tmp_path, kind, cancel):
    path = tmp_path/'control.sqlite3'
    repository = AsyncControlPlaneExecutionRepository(path)
    original = await save(repository, kind, initial(kind))
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        async with SQLiteControlPlaneTransactions(path)() as transaction:
            advanced = await save(transaction.execution, kind, changed(original, kind))
            assert advanced.state_revision == 1
            raise asyncio.CancelledError('interrupt') if cancel else RuntimeError('interrupt')
    assert await read(repository, kind) == original
    assert (await save(repository, kind, changed(original, kind))).state_revision == 1
