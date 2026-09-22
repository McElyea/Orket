"""Canonical ASGI/runtime/SQLite admission; no tool dispatch or inference."""
import json
from pathlib import Path

import aiosqlite
import httpx
import pytest

from orket.interfaces.api import create_api_app
from tests.helpers.kernel_runtime import engine_events
from tests.helpers.outward_authorization import TEST_API_KEY

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('enabled', [True, False])
async def test_api_request_cannot_replace_operator_policy_and_retains_actual_publication(tmp_path, monkeypatch, enabled):
    for key, value in {'ORKET_ENABLE_NERVOUS_SYSTEM': str(enabled).lower(),
            'ORKET_USE_TOOL_PROFILE_RESOLVER': 'true', 'ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS': 'false'}.items():
        monkeypatch.setenv(key, value)
    environment = {'ORKET_API_KEY': TEST_API_KEY, 'ORKET_DISABLE_SANDBOX': '1',
        'ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED': '0', 'ORKET_TTS_BACKEND': 'null',
        'ORKET_STATE_BACKEND_MODE': 'local', 'ORKET_RUN_LEDGER_MODE': 'sqlite',
        'ORKET_DURABLE_ROOT': str(tmp_path / 'state'), 'ORKET_GITEA_ARTIFACT_EXPORT': '0'}
    app = create_api_app(project_root=tmp_path, environment=environment)
    request = {'session_id': 'api-policy', 'trace_id': 'first',
        'policy_inputs': {'enabled': True, 'allow_pre_resolved_flags': True, 'use_profile_resolver': False},
        'proposal': {'proposal_type': 'action.tool_call', 'payload': {'tool_name': 'fs.delete',
            'args': {'path': './workspace/important.txt'}}}}
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        engine = owner.engine
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://api.test') as client:
            assert (await client.post('/v1/kernel/admit-proposal', json=request)).status_code == 403
            assert await engine_events(engine, 'api-policy') == []
            response = await client.post('/v1/kernel/admit-proposal', json=request, headers={'X-API-Key': TEST_API_KEY})
            if enabled:
                assert response.status_code == 200
                assert response.json()['admission_decision'] == {'decision': 'REJECT', 'reason_codes': ['SCOPE_VIOLATION']}
                await assert_sqlite_decision(owner.engine, 'first', response.json())
            else:
                assert response.status_code == 400 and 'disabled' in response.json()['detail']
                assert await engine_events(engine, 'api-policy') == []
            monkeypatch.setenv('ORKET_ENABLE_NERVOUS_SYSTEM', 'true')
            monkeypatch.setenv('ORKET_USE_TOOL_PROFILE_RESOLVER', 'false')
            request['trace_id'] = 'second'
            response = await client.post('/v1/kernel/admit-proposal', json=request, headers={'X-API-Key': TEST_API_KEY})
            assert response.status_code == 200
            assert response.json()['admission_decision'] == {'decision': 'NEEDS_APPROVAL', 'reason_codes': ['UNKNOWN_TOOL_PROFILE']}
            await assert_sqlite_decision(owner.engine, 'second', response.json())
    assert owner.closed

async def assert_sqlite_decision(engine, trace, response):
    database = Path(engine.control_plane_execution_repository.db_path)
    async with aiosqlite.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
        cursor = await connection.execute('SELECT payload_json FROM control_plane_runs WHERE run_id = ?',
            (f'kernel-action-run:api-policy:{trace}',))
        run = json.loads((await cursor.fetchone())[0])
        cursor = await connection.execute('SELECT payload_json FROM resolved_policy_snapshots WHERE snapshot_id = ?',
            (run['policy_snapshot_id'],))
        snapshot = json.loads((await cursor.fetchone())[0])
    assert run['policy_digest'] == response['decision_digest']
    assert snapshot['policy_payload']['admission_decision'] == response['admission_decision']
    admitted, = [event for event in await engine_events(engine, 'api-policy')
        if event['trace_id'] == trace and event['event_type'] == 'admission.decided']
    assert admitted['body']['decision_digest'] == run['policy_digest']
