"""Layer: integration. Public ASGI routes retain application-owned input and authorization scope."""
import asyncio
import json
import os
from contextlib import AsyncExitStack
from datetime import UTC, datetime

import httpx
import pytest

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.interfaces.api import create_api_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _request(app, key, path='/v1/system/heartbeat', **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        return await client.get(path, headers={'X-API-Key': key}, **kwargs)


async def test_api_app_authentication_keeps_its_captured_key(tmp_path, monkeypatch):
    monkeypatch.setenv('ORKET_API_KEY', 'application-a')
    first = create_api_app(project_root=tmp_path/'first')
    monkeypatch.setenv('ORKET_API_KEY', 'application-b')
    second = create_api_app(project_root=tmp_path/'second')
    async with first.router.lifespan_context(first), second.router.lifespan_context(second):
        responses = await asyncio.gather(
            _request(first, 'application-a'), _request(first, 'application-b'),
            _request(second, 'application-b'), _request(second, 'application-a'),
        )
        assert [response.status_code for response in responses] == [200, 403, 200, 403]
    assert first.state.api_runtime_context.closed and second.state.api_runtime_context.closed


async def test_api_strategy_cannot_authorize_an_invalid_key(tmp_path, monkeypatch):
    monkeypatch.setenv('ORKET_API_KEY', 'expected-key')
    app = create_api_app(project_root=tmp_path)
    async with app.router.lifespan_context(app):
        monkeypatch.setattr(app.state.api_runtime_context.api_runtime_node, 'is_api_key_valid',
                            lambda *args: True, raising=False)
        response = await _request(app, 'incorrect-key')
        assert response.status_code == 403
    assert app.state.api_runtime_context.closed


async def test_api_board_uses_each_application_root(tmp_path, monkeypatch):
    monkeypatch.setenv('ORKET_API_KEY', 'expected-key')
    applications = []
    for name in ('first', 'second'):
        root = tmp_path/name
        issues = root/'model'/'core'/'issues'
        await asyncio.to_thread(issues.mkdir, parents=True)
        await asyncio.to_thread((issues/'card.json').write_text,
                                json.dumps({'id': name, 'summary': name}), encoding='utf-8')
        applications.append(create_api_app(project_root=root))
    async with AsyncExitStack() as lifetimes:
        for app in applications:
            await lifetimes.enter_async_context(app.router.lifespan_context(app))
        responses = await asyncio.gather(*[
            _request(app, 'expected-key', '/v1/system/board') for app in applications
        ])
        assert [response.status_code for response in responses] == [200, 200]
        assert [[issue['id'] for issue in response.json()['orphaned_issues']]
                for response in responses] == [['first'], ['second']]
        boards = await asyncio.gather(*[
            asyncio.to_thread(app.state.api_runtime_context.engine.get_board) for app in applications
        ])
        assert [[issue['id'] for issue in board['orphaned_issues']] for board in boards] == [['first'], ['second']]
    assert all(app.state.api_runtime_context.closed for app in applications)


async def test_api_strategy_cannot_override_explorer_containment(tmp_path, monkeypatch):
    monkeypatch.setenv('ORKET_API_KEY', 'expected-key')
    outside = tmp_path/'outside'
    await asyncio.to_thread(outside.mkdir)
    await asyncio.to_thread((outside/'private-fixture.txt').write_text, 'fixture')
    app = create_api_app(project_root=tmp_path/'application')
    async with app.router.lifespan_context(app):
        monkeypatch.setattr(app.state.api_runtime_context.api_runtime_node, 'resolve_explorer_path',
                            lambda *args: outside, raising=False)
        response = await _request(app, 'expected-key', '/v1/system/explorer', params={'path': '../outside'})
        assert response.status_code == 403
        assert 'private-fixture.txt' not in response.text
    assert app.state.api_runtime_context.closed


async def test_api_captures_caller_settings_for_auth_calendar_and_cors(tmp_path, monkeypatch):
    class FixedInputs(RuntimeInputService):
        def utc_now(self):
            return datetime(2026, 2, 10, 3, tzinfo=UTC)

    environment = {**os.environ, 'ORKET_API_KEY': 'original', 'ORKET_ALLOWED_ORIGINS': 'https://original.example',
                   'ORKET_EOS_SPRINT_BASE_DATE': '2026-02-02', 'ORKET_EOS_SPRINT_BASE_QUARTER': '3',
                   'ORKET_EOS_SPRINT_BASE_SPRINT': '12', 'ORKET_TIMEZONE': 'MST'}
    app = create_api_app(project_root=tmp_path, environment=environment, runtime_inputs=FixedInputs())
    environment.update(ORKET_API_KEY='replaced', ORKET_EOS_SPRINT_BASE_QUARTER='9',
                       ORKET_ALLOWED_ORIGINS='https://replaced.example', ORKET_TIMEZONE='UTC')
    monkeypatch.setenv('ORKET_EOS_SPRINT_BASE_QUARTER', '20')
    async with app.router.lifespan_context(app):
        response = await _request(app, 'original', '/v1/system/calendar')
        assert response.status_code == 200
        assert response.json() == {'current_sprint': 'Q3 S13', 'sprint_start': '2026-02-09',
                                   'sprint_end': '2026-02-13'}
        assert (await _request(app, 'replaced')).status_code == 403
        heartbeat = await _request(app, 'original')
        assert heartbeat.json()['timestamp'] == '2026-02-09T20:00:00-07:00'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            for origin, status in [('https://original.example', 200), ('https://replaced.example', 400)]:
                preflight = await client.options('/v1/system/heartbeat', headers={
                    'Origin': origin, 'Access-Control-Request-Method': 'GET'})
                assert preflight.status_code == status


async def test_api_explorer_and_metrics_observe_selected_workspace(tmp_path):
    await asyncio.to_thread((tmp_path/'visible').mkdir)
    await asyncio.to_thread((tmp_path/'.hidden').mkdir)
    await asyncio.to_thread((tmp_path/'note.txt').write_text, 'observed')
    run = tmp_path/'workspace'/'runs'/'selected'
    await asyncio.to_thread(run.mkdir, parents=True)
    await asyncio.to_thread((run/'orket.log').write_text, json.dumps({
        'role': 'coder', 'event': 'model_usage', 'data': {'total_tokens': 73},
    })+'\n', encoding='utf-8')
    app = create_api_app(project_root=tmp_path, environment={**os.environ, 'ORKET_API_KEY': 'expected'})
    async with app.router.lifespan_context(app):
        context = app.state.api_runtime_context
        response = await _request(app, 'expected', '/v1/system/explorer')
        assert response.status_code == 200
        assert response.json()['items'] == [
            {'name': 'visible', 'is_dir': True, 'ext': ''},
            {'name': 'workspace', 'is_dir': True, 'ext': ''},
            {'name': 'note.txt', 'is_dir': False, 'ext': '.txt'},
            {'name': 'orket.log', 'is_dir': False, 'ext': '.log'},
        ]
        missing = await _request(app, 'expected', '/v1/system/explorer', params={'path': 'absent'})
        assert missing.json() == {'items': [], 'path': 'absent'}
        assert await context.system_queries.member_metrics_workspace('selected') == run
        assert await context.system_queries.member_metrics_workspace('absent') == tmp_path/'workspace'/'default'
        metrics = await _request(app, 'expected', '/v1/runs/selected/metrics')
        assert metrics.status_code == 200
        assert metrics.json()['coder']['tokens'] == 73
        with pytest.raises(PermissionError):
            await context.system_queries.member_metrics_workspace('../../outside')
