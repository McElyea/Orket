"""Configured calendar observations through real assets, SQLite and owned workers."""
import asyncio
import json
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.runtime.execution import epic_run_orchestrator as epic_module
from orket.time_utils import configured_timezone
from tests.integration.test_execution_policy_input_capture import hold_asset, pipeline_at

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def calendar_owner(root, environment, stamp, monkeypatch):
    pipeline = await pipeline_at(root)
    pipeline.runtime_context.construction_inputs = RuntimeConstructionInputs(root, environment, '{}', '{}')
    monkeypatch.setattr(pipeline.runtime_inputs, 'utc_now', lambda: datetime.fromisoformat(stamp))
    return pipeline, pipeline._build_epic_run_orchestrator()


async def setup_for(owner):
    return await owner._load_setup(epic_name='publication_epic', build_id='zone-build',
        session_id='zone-session', target_issue_id=None, model_override='')


@pytest.mark.parametrize('index', range(14))
async def test_published_timezone_outcome_reaches_actual_sqlite_card(tmp_path, monkeypatch, index):
    files = AsyncFileTools(Path(__file__).parents[1] / 'fixtures')
    cases = json.loads(await files.read_file('epic_calendar_timezones_v051.json'))['cases']
    case = cases[index]
    pipeline, owner = await calendar_owner(tmp_path, case['environment'], case['utc'], monkeypatch)
    try:
        await owner._ensure_session_and_cards(await setup_for(owner))
        card = await pipeline.async_cards.get_by_id('ISSUE-1')
        assert card.sprint == case['sprint'], case
    finally:
        await pipeline.close()


@pytest.mark.parametrize(('environment', 'expected'), [({}, 'Q3 S2'), ({'ORKET_TIMEZONE': 'MST'}, 'Q3 S1')])
async def test_owner_captures_timezone_and_clock_before_asset_reads(tmp_path, monkeypatch, environment, expected):
    monkeypatch.setenv('ORKET_TIMEZONE', 'MST')
    pipeline, owner = await calendar_owner(tmp_path, environment, '2026-07-06T06:30:00+00:00', monkeypatch)
    entered, release = hold_asset(pipeline.loader, monkeypatch)
    environment['ORKET_TIMEZONE'] = 'UTC'
    monkeypatch.setenv('ORKET_TIMEZONE', 'UTC')
    operation = asyncio.create_task(setup_for(owner))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        monkeypatch.setattr(pipeline.runtime_inputs, 'utc_now', lambda: datetime.fromisoformat('2026-08-01T12:00:00+00:00'))
        release.set()
        await owner._ensure_session_and_cards(await asyncio.wait_for(operation, 5))
        assert (await pipeline.async_cards.get_by_id('ISSUE-1')).sprint == expected
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        await pipeline.close()


async def test_owner_without_construction_snapshot_captures_environment(tmp_path, monkeypatch):
    for suffix, value in (('DATE', '2026-02-02'), ('QUARTER', '1'), ('SPRINT', '6')):
        monkeypatch.setenv('ORKET_EOS_SPRINT_BASE_' + suffix, value)
    pipeline = await pipeline_at(tmp_path)
    pipeline.runtime_context.construction_inputs = None
    monkeypatch.setenv('ORKET_TIMEZONE', 'MST')
    monkeypatch.setattr(pipeline.runtime_inputs, 'utc_now', lambda: datetime.fromisoformat('2026-07-06T06:30:00+00:00'))
    owner = pipeline._build_epic_run_orchestrator()
    monkeypatch.setenv('ORKET_TIMEZONE', 'UTC')
    try:
        await owner._ensure_session_and_cards(await setup_for(owner))
        assert (await pipeline.async_cards.get_by_id('ISSUE-1')).sprint == 'Q3 S1'
    finally:
        await pipeline.close()


async def test_clock_observation_precedes_owned_timezone_lookup(tmp_path, monkeypatch):
    pipeline, owner = await calendar_owner(tmp_path, {}, '2026-02-02T01:00:00+00:00', monkeypatch)
    entered, release = threading.Event(), threading.Event()

    def held_zone(name):
        result = configured_timezone(name)
        entered.set()
        assert release.wait(5), 'timezone lookup was not released'
        return result

    monkeypatch.setattr(epic_module, 'configured_timezone', held_zone)
    operation = asyncio.create_task(setup_for(owner))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        monkeypatch.setattr(pipeline.runtime_inputs, 'utc_now', lambda: datetime.fromisoformat('2026-02-09T12:00:00+00:00'))
        monkeypatch.setenv('ORKET_TIMEZONE', 'MST')
        release.set()
        await owner._ensure_session_and_cards(await asyncio.wait_for(operation, 5))
        assert (await pipeline.async_cards.get_by_id('ISSUE-1')).sprint == 'Q1 S6'
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        await pipeline.close()


@pytest.mark.parametrize('interruption', ['cancel', 'timeout', 'worker_failure'])
async def test_calendar_worker_is_responsive_and_owned_through_interruption(tmp_path, monkeypatch, record_property, interruption):
    pipeline, owner = await calendar_owner(tmp_path, {}, '2026-02-02T01:00:00+00:00', monkeypatch)
    await AsyncFileTools(tmp_path).write_file('zone-resource.txt', 'UTC')
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    handles = []

    def held_zone(name):
        try:
            with (tmp_path / 'zone-resource.txt').open(encoding='utf-8') as handle:
                handles.append(handle)
                assert handle.read() == 'UTC'
                zone = configured_timezone(name)
                entered.set()
                assert release.wait(5), 'calendar worker was not released'
                if interruption == 'worker_failure':
                    raise OSError('zone-read-failed')
                return zone
        finally:
            finished.set()

    monkeypatch.setattr(epic_module, 'configured_timezone', held_zone)
    operation = asyncio.create_task(setup_for(owner))
    waiter = operation
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        started = time.monotonic()
        assert await asyncio.wait_for(pipeline.async_cards.get_by_id('ISSUE-1'), 0.5) is None
        elapsed = time.monotonic() - started
        record_property('responsive_sqlite_seconds', elapsed)
        assert elapsed < 0.5  # Existing D1 responsiveness acceptance bound.
        if interruption == 'timeout':
            waiter = asyncio.create_task(asyncio.wait_for(operation, 0.01))
            await asyncio.sleep(0.05)
        else:
            for _ in range(2):
                operation.cancel()
                await asyncio.sleep(0)
        assert not operation.done() and not waiter.done() and not finished.is_set()
        release.set()
        error = {'cancel': asyncio.CancelledError, 'timeout': TimeoutError, 'worker_failure': OSError}[interruption]
        with pytest.raises(error):
            await asyncio.wait_for(waiter, 5)
        assert finished.is_set() and all(handle.closed for handle in handles)
        assert await pipeline.async_cards.get_by_id('ISSUE-1') is None
    finally:
        release.set()
        await asyncio.gather(operation, waiter, return_exceptions=True)
        await pipeline.close()
