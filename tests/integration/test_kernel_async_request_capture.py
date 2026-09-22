"""Public engine kernel invocation keeps its admitted caller values across SQLite waits."""
import asyncio
import json
from pathlib import Path

import aiosqlite
import pytest

from orket.core.domain import OperatorInputClass
from orket.interfaces.api import create_api_app
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_kernel_publication_input_capture import hold_first_lookup

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('operation', ['admit_proposal', 'commit_proposal', 'end_session'])
async def test_public_engine_retains_kernel_target_and_operator_input(tmp_path, monkeypatch, operation):
    for key, value in {'ORKET_ENABLE_NERVOUS_SYSTEM': 'true', 'ORKET_USE_TOOL_PROFILE_RESOLVER': 'true'}.items():
        monkeypatch.setenv(key, value)
    app = create_api_app(project_root=tmp_path, environment={'ORKET_API_KEY': TEST_API_KEY,
        'ORKET_DISABLE_SANDBOX': '1', 'ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED': '0', 'ORKET_TTS_BACKEND': 'null',
        'ORKET_STATE_BACKEND_MODE': 'local', 'ORKET_RUN_LEDGER_MODE': 'sqlite',
        'ORKET_DURABLE_ROOT': str(tmp_path / 'state'), 'ORKET_GITEA_ARTIFACT_EXPORT': '0'})
    request = {'contract_version': 'kernel_api/v1', 'session_id': 'original', 'trace_id': 'trace',
        'proposal': {'proposal_type': 'action.tool_call', 'payload': {'tool_name': 'local.echo'}},
        'operator_actor_ref': 'operator:original', 'reason': 'original', 'attestation_scope': 'run_scope',
        'attestation_payload': {'note': ['original']}}
    async with app.router.lifespan_context(app):
        owner, engine = app.state.api_runtime_context, app.state.api_runtime_context.engine
        if operation != 'admit_proposal':
            admitted = await engine.kernel_admit_proposal_async(request)
            request.update(proposal_digest=admitted['proposal_digest'],
                admission_decision_digest=admitted['decision_digest'], execution_result_digest='a' * 64)
        entered, release = hold_first_lookup(monkeypatch, engine.control_plane_execution_repository)
        task = asyncio.create_task(getattr(engine, 'kernel_' + operation + '_async')(request))
        try:
            await asyncio.wait_for(entered.wait(), timeout=10)
            request['session_id'] = 'rotated'
            request['operator_actor_ref'] = 'operator:rotated'
            request['attestation_payload']['note'][0] = 'rotated'
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
        response = await task
        assert response['control_plane_run_id'] == 'kernel-action-run:original:trace'
        if operation == 'end_session':
            database = Path(engine.control_plane_execution_repository.db_path)
            async with aiosqlite.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
                cursor = await connection.execute('SELECT payload_json FROM operator_action_records')
                rows = [json.loads(row[0]) for row in await cursor.fetchall()]
            assert len(rows) == 2 and all(row['actor_ref'] == 'operator:original' for row in rows)
            attestation, = [row for row in rows if row['input_class'] == OperatorInputClass.ATTESTATION.value]
            assert attestation['attestation_payload'] == {'note': ['original']}
    assert owner.closed
