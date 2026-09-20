"""Integration counterexample: queued admission must retain its selected files/store."""
import asyncio
import dataclasses
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from orket.application.services import governed_agent_submission_service as owner
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_governed_agent_submission_ownership import submission_for

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('relative_submission', [False, True])
@pytest.mark.parametrize('relative_database', [False, True])
@pytest.mark.parametrize('explicit_root', [False, True])
async def test_queued_submission_retains_admitted_locations(
    tmp_path, monkeypatch, relative_submission, relative_database, explicit_root,
):
    initial, rotated = tmp_path / 'initial', tmp_path / 'rotated'
    await asyncio.to_thread(initial.mkdir)
    await asyncio.to_thread(rotated.mkdir)
    submission = await asyncio.to_thread(submission_for, initial)
    alternate = await asyncio.to_thread(submission_for, rotated)
    admitted = json.loads(await asyncio.to_thread(submission.request_path.read_text, encoding='utf-8'))
    replacement = json.loads(await asyncio.to_thread(alternate.request_path.read_text, encoding='utf-8'))
    replacement['identity']['run_id'] = 'rotated-submission-run'
    await asyncio.to_thread(alternate.request_path.write_text, json.dumps(replacement), encoding='utf-8')
    await asyncio.to_thread((initial / 'continuation.json').write_text, '{}', encoding='utf-8')
    await asyncio.to_thread((rotated / 'continuation.json').write_text, '[]', encoding='utf-8')
    submission = dataclasses.replace(submission, continuation_inputs_path=initial / 'continuation.json')
    if relative_submission:
        submission = dataclasses.replace(submission, project_root=Path(), catalog_path=Path('catalog.json'),
                                         request_path=Path('request.json'), continuation_inputs_path=Path('continuation.json'))
    now = datetime.fromisoformat(submission.creation_timestamp_utc)
    submission = dataclasses.replace(submission,
        decision_timestamps_utc=((now + timedelta(seconds=1)).isoformat(), (now + timedelta(seconds=2)).isoformat()),
        next_lease_expiries_utc=(admitted['lease_expires_at_utc'],))
    database = Path('agent.sqlite3') if relative_database else initial / 'agent.sqlite3'
    competing = rotated / 'agent.sqlite3'
    before = await asyncio.to_thread(_competing_store, competing)
    entered, release = asyncio.Event(), asyncio.Event()
    original = owner.run_owned_thread

    async def held(operation, **kwargs):
        entered.set()
        await release.wait()
        return await original(operation, **kwargs)

    monkeypatch.setattr(owner, 'run_owned_thread', held)
    monkeypatch.chdir(rotated if explicit_root else initial)
    task = asyncio.create_task(owner.submit_governed_agent(
        db_path=database, submission=submission, invocation_root=initial if explicit_root else None,
    ))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        monkeypatch.chdir(rotated)
        release.set()
        result = await asyncio.wait_for(task, 30)
        assert result['ok'] is True
        assert result['run']['run_id'] == admitted['identity']['run_id']
        assert result['db_path'] == str(initial / 'agent.sqlite3')
        assert await asyncio.to_thread((initial / 'agent.sqlite3').is_file)
        assert await asyncio.to_thread(competing.read_bytes) == before
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


def _competing_store(path):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute('CREATE TABLE untouched (value TEXT)')
        connection.execute("INSERT INTO untouched VALUES ('retain')")
    return path.read_bytes()


async def test_relative_invocation_root_refuses_before_worker_or_store(tmp_path, monkeypatch):
    submission = await asyncio.to_thread(submission_for, tmp_path)
    entered = False

    async def unexpected_worker(*_args, **_kwargs):
        nonlocal entered
        entered = True
        raise AssertionError('invalid root must refuse before worker scheduling')

    monkeypatch.setattr(owner, 'run_owned_thread', unexpected_worker)
    with pytest.raises(ValueError, match='E_AGENT_INVOCATION_ROOT_ABSOLUTE_REQUIRED'):
        await owner.submit_governed_agent(db_path=tmp_path / 'agent.sqlite3', submission=submission,
                                         invocation_root=Path('relative'))
    assert not entered and not await asyncio.to_thread((tmp_path / 'agent.sqlite3').exists)


@pytest.mark.parametrize('explicit_environment', [False, True])
async def test_queued_submission_uses_captured_environment_for_inventory(tmp_path, monkeypatch, explicit_environment):
    submission = await asyncio.to_thread(submission_for, tmp_path)
    submission = dataclasses.replace(submission, provider=owner.GovernedAgentProviderOptions(
        provider_name='openai_compat', model='qwen-fixture', inventory_timeout_seconds=5,
    ))
    entered, release = asyncio.Event(), asyncio.Event()
    original = owner.run_owned_thread

    async def held(operation, **kwargs):
        entered.set()
        await release.wait()
        return await original(operation, **kwargs)

    async def unavailable_inventory(_):
        return 200, {'data': []}

    monkeypatch.setattr(owner, 'run_owned_thread', held)
    async with (observed_http_server(unavailable_inventory) as (first, first_requests),
                observed_http_server(unavailable_inventory) as (second, second_requests)):
        monkeypatch.setenv('ORKET_LLM_OPENAI_BASE_URL', first + '/v1')
        monkeypatch.setenv('ORKET_PROVIDER_QUARANTINE', '')
        for name in ['ORKET_LLM_OPENAI_API_KEY', 'ORKET_MODEL_STREAM_OPENAI_API_KEY']:
            monkeypatch.setenv(name, '')
        environment = dict(os.environ) if explicit_environment else None
        task = asyncio.create_task(owner.submit_governed_agent(
            db_path=tmp_path / 'agent.sqlite3', submission=submission, environment=environment,
        ))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            monkeypatch.setenv('ORKET_LLM_OPENAI_BASE_URL', second + '/v1')
            monkeypatch.setenv('ORKET_PROVIDER_QUARANTINE', 'openai_compat')
            if environment is not None:
                environment.update(os.environ)
            release.set()
            with pytest.raises(ValueError, match='E_AGENT_LOCAL_MODEL_UNAVAILABLE:planner:qwen-fixture'):
                await asyncio.wait_for(task, 10)
            assert first_requests and all(line.startswith('GET ') for line, _ in first_requests)
            assert not second_requests and not await asyncio.to_thread((tmp_path / 'agent.sqlite3').exists)
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
