"""Public ASGI wake ingress uses the factory's provider inputs over real TCP."""
import asyncio
import json
import os

import aiosqlite
import httpx
import pytest

from orket.interfaces.api import create_api_app
from tests.helpers.governed_agent_cli import write_submission_files
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_governed_agent_wake_dispatcher import _wake

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]


@pytest.mark.parametrize('rotate', ['before_lifespan', 'after_lifespan'])
async def test_api_wake_uses_factory_provider_environment(tmp_path, monkeypatch, rotate):
    catalog, request_path, now = await asyncio.to_thread(write_submission_files, tmp_path)
    request = json.loads(await asyncio.to_thread(request_path.read_text, encoding='utf-8'))
    payload = dict(occurrence_id='api-capture', target_kind='new_run', workload_id='governed-agent-loop',
                   dispatch=dict(_wake(request, now).payload))

    async def unavailable(_):
        return 200, {'data': []}

    async with (observed_http_server(unavailable) as (first, first_requests),
                observed_http_server(unavailable) as (second, second_requests)):
        environment = dict(os.environ, ORKET_API_KEY=TEST_API_KEY, ORKET_EXTENSIONS_CATALOG=str(catalog),
            ORKET_DURABLE_ROOT=str(tmp_path / 'state'), ORKET_GOVERNED_AGENT_DB_PATH=str(tmp_path / 'agent.sqlite3'),
            ORKET_GOVERNED_AGENT_PROVIDER='openai_compat', ORKET_GOVERNED_AGENT_MODEL='qwen-fixture',
            ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED='1', ORKET_GOVERNED_AGENT_BASE_URL='',
            ORKET_GOVERNED_AGENT_INVENTORY_TIMEOUT_SECONDS='5', ORKET_LLM_PROVIDER='openai_compat',
            ORKET_LLM_OPENAI_BASE_URL=first + '/v1', ORKET_LLM_OPENAI_API_KEY='',
            ORKET_MODEL_STREAM_OPENAI_API_KEY='', ORKET_PROVIDER_QUARANTINE='', ORKET_TTS_BACKEND='null',
            ORKET_DISABLE_SANDBOX='1')
        app = create_api_app(project_root=tmp_path, environment=environment)

        def mutate():
            environment['ORKET_LLM_OPENAI_BASE_URL'] = second + '/v1'
            monkeypatch.setenv('ORKET_LLM_OPENAI_BASE_URL', second + '/v1')
            monkeypatch.setenv('ORKET_PROVIDER_QUARANTINE', 'openai_compat')

        if rotate == 'before_lifespan':
            mutate()
        async with app.router.lifespan_context(app):
            if rotate == 'after_lifespan':
                mutate()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://api.test') as client:
                headers = {'X-API-Key': TEST_API_KEY}
                admitted = await client.post('/v1/agent-wakes', headers=headers, json=payload)
                assert admitted.status_code == 202
                wake_id = admitted.json()['wake']['wake_id']
                async with asyncio.timeout(10):
                    while True:
                        retained = await client.get(f'/v1/agent-wakes/{wake_id}', headers=headers)
                        assert retained.status_code == 200
                        if retained.json()['state'] == 'recovery_required':
                            break
                        await asyncio.sleep(0.01)
                assert retained.json()['last_reason'] == 'dispatch_failed:ValueError'
                inspection = await client.get('/v1/agent-runs/run-1', headers=headers)
                assert inspection.status_code == 409
                assert inspection.json()['detail'] == 'E_AGENT_TERMINAL_AUTHORITY_CONFLICT:history_unreadable'
                await _assert_no_run_inventory(tmp_path / 'agent.sqlite3')
        assert first_requests and not second_requests
        assert app.state.api_runtime_context.closed
        assert app.state.api_runtime_context.active_background_task_count == 0


async def _assert_no_run_inventory(path):
    async with (aiosqlite.connect(path.as_uri() + '?mode=ro', uri=True) as connection,
                connection.execute("SELECT 1 FROM sqlite_master WHERE name='control_plane_runs'") as cursor):
        assert await cursor.fetchone() is None
