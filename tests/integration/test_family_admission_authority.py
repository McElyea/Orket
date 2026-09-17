"""BT-5.3–5: one admission interruption through each composed family path."""
import asyncio
import json

import aiosqlite
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_authorization import outward_api
from tests.integration.test_epic_completion_publication import publication_pipeline
from tests.integration.test_family_terminal_authority import card_flow, run_agent_fixture
from tests.runtime.governed_agent_test_support import TEMPLATE_ROOT, agent_request

pytestmark = [pytest.mark.asyncio, pytest.mark.integration, pytest.mark.usefixtures("elapsed_agent_clock")]
FAULT = 'bt5-family-parent-admission-interrupted'


@pytest.mark.parametrize('family', ['outward', 'cards', 'governed_agent'])
@pytest.mark.parametrize('interrupt', [False, True], ids=['healthy', 'attempt-interrupted'])
# Layer: integration
async def test_family_admission_cannot_retain_parent_without_attempt(
    family, interrupt, tmp_path, test_root, workspace, db_path, boundary, monkeypatch,
):
    original = AsyncControlPlaneExecutionRepository.save_attempt_record
    called = []

    async def save_attempt(repository, *, record):
        if interrupt and not called:
            called.append((repository.db_path, record.run_id))
            raise RuntimeError(FAULT)
        return await original(repository, record=record)

    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, 'save_attempt_record', save_attempt)
    try:
        if family == 'outward':
            db, inputs, calls = boundary
            async with outward_api(tmp_path, inputs) as (client, context):
                response = await client.post('/v1/runs', json={
                    'run_id': 'bt5-admission', 'task': {'description': 'Admission interruption',
                    'instruction': 'Execute an approved fixture call.',
                    'acceptance_contract': {'governed_tool_sequence': calls[:1]}},
                    'policy_overrides': {'approval_required_tools': ['write_file'], 'max_turns': 1},
                })
                observed = {'status': response.status_code, 'body': response.json()}
                assert response.status_code == (409 if interrupt else 200), observed
            assert context.closed
        elif family == 'cards':
            db, observed = await card_flow(test_root, workspace, db_path, monkeypatch)
        else:
            source = await asyncio.to_thread((TEMPLATE_ROOT / 'governed_agent.py').read_text, encoding='utf-8')
            outcome, _ = await run_agent_fixture(tmp_path, source, agent_request())
            db, observed = tmp_path / 'agent.sqlite3', {'lifecycle': outcome.run.lifecycle_state.value}
    except RuntimeError as exc:
        assert str(exc) == FAULT
        db, _ = called[0]
        observed = {'error': str(exc)}
    async with aiosqlite.connect('file:' + str(db) + '?mode=ro', uri=True) as connection:
        cursor = await connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in await cursor.fetchall()}
        rows = {}
        for table in ('control_plane_runs', 'control_plane_attempts'):
            if table in tables:
                cursor = await connection.execute('SELECT payload_json FROM ' + table)
                rows[table] = [json.loads(row[0]) for row in await cursor.fetchall()]
            else:
                rows[table] = []
    runs, attempts = rows['control_plane_runs'], rows['control_plane_attempts']
    orphaned = [run for run in runs if not any(attempt['attempt_id'] == run['current_attempt_id']
                and attempt['run_id'] == run['run_id'] for attempt in attempts)]
    if interrupt:
        assert called, observed
    else:
        assert runs and attempts, observed
        if family == "cards":
            assert all((await admission_rows(db)).values())
    assert not orphaned, {'family': family, 'observed': observed, 'orphaned': orphaned}


ADMISSION_WRITES = [
    (AsyncControlPlaneRecordRepository, "save_resolved_policy_snapshot"),
    (AsyncControlPlaneRecordRepository, "save_resolved_configuration_snapshot"),
    (AsyncControlPlaneExecutionRepository, "save_run_record"),
    (AsyncControlPlaneExecutionRepository, "save_attempt_record"),
    (AsyncControlPlaneExecutionRepository, "save_step_record"),
    (AsyncControlPlaneRecordRepository, "append_effect_journal_entry"),
    (AsyncControlPlaneRecordRepository, "save_checkpoint"),
    (AsyncControlPlaneRecordRepository, "save_checkpoint_acceptance"),
]
ADMISSION_TABLES = (
    "resolved_policy_snapshots", "resolved_configuration_snapshots", "control_plane_runs",
    "control_plane_attempts", "control_plane_steps", "effect_journal_entries",
    "checkpoint_records", "checkpoint_acceptance_records",
)


async def admission_rows(db):
    async with aiosqlite.connect("file:" + str(db) + "?mode=ro", uri=True) as connection:
        cursor = await connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in await cursor.fetchall()}
        counts = {}
        for table in ADMISSION_TABLES:
            if table in tables:
                cursor = await connection.execute("SELECT COUNT(*) FROM " + table)
                counts[table] = (await cursor.fetchone())[0]
            else:
                counts[table] = 0
    return counts


@pytest.mark.parametrize("repository_type,method", ADMISSION_WRITES, ids=[method for _, method in ADMISSION_WRITES])
@pytest.mark.parametrize("cancel", [False, True], ids=["exception", "cancelled"])
# Layer: integration
async def test_cards_admission_rolls_back_every_record_before_dispatch(
    repository_type, method, cancel, test_root, workspace, db_path, monkeypatch,
):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    db = pipeline.orchestrator.control_plane_execution_repository.db_path
    original = getattr(repository_type, method)
    interrupted, dispatched = [], []
    reached = asyncio.Event()

    async def interrupted_write(repository, **kwargs):
        result = await original(repository, **kwargs)
        if not interrupted:
            interrupted.append(result)
            if cancel:
                reached.set()
                await asyncio.Event().wait()
            raise RuntimeError(FAULT)
        return result

    async def work(**_kwargs):
        dispatched.append(True)

    monkeypatch.setattr(repository_type, method, interrupted_write)
    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", work)
    try:
        if cancel:
            task = asyncio.create_task(pipeline.run_card("publication_epic", build_id="build", session_id="admission-rollback"))
            try:
                await asyncio.wait_for(reached.wait(), timeout=10)
            finally:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
        else:
            observed = await pipeline.run_card("publication_epic", build_id="build", session_id="admission-rollback")
            assert not observed.succeeded and FAULT in observed.reason
    finally:
        await pipeline.close()
    assert interrupted and not dispatched
    counts = await admission_rows(db)
    assert not any(counts.values()), counts
