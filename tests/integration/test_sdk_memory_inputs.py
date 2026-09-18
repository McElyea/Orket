"""Layer: integration. Real SDK bridge and SQLite publication with borrowed-input mutation."""
import asyncio
import threading
import traceback
from contextlib import contextmanager

import pytest

from orket.application.services.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket_extension_sdk.memory import MemoryQueryRequest, MemoryWriteRequest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@contextmanager
def _held_storage(provider):
    entered, release = threading.Event(), threading.Event()
    original = provider._store.ensure_initialized

    async def hold_initialization():
        entered.set()
        assert await asyncio.to_thread(release.wait, 10), 'probe did not release storage'
        await original()

    provider._store.ensure_initialized = hold_initialization
    try:
        yield entered, release
    finally:
        release.set()
        provider._store.ensure_initialized = original


@pytest.mark.parametrize('scope', ['session_memory', 'profile_memory'])
@pytest.mark.parametrize('mutate', [False, True], ids=['unchanged', 'mutated'])
async def test_sdk_memory_captures_nested_write_input_before_bridge_storage_await(tmp_path, scope, mutate):
    provider = SQLiteMemoryCapabilityProvider(tmp_path/'memory.sqlite3', extension_id='capture-probe')
    key = 'topic' if scope == 'session_memory' else 'companion_setting.theme'
    request = MemoryWriteRequest(scope=scope, key=key, value='captured value', session_id='session-a',
                                 metadata={'nested': {'values': ['captured']}})
    with _held_storage(provider) as (entered, release):
        task = asyncio.create_task(asyncio.to_thread(provider.write, request))
        try:
            assert await asyncio.to_thread(entered.wait, 10), 'bridge did not reach storage'
            if mutate:
                request.metadata['nested']['values'].append('MUTATED')
        finally:
            release.set()
            response, = await asyncio.gather(task, return_exceptions=True)
    assert not isinstance(response, BaseException) and response.ok, response
    query = MemoryQueryRequest(scope=scope, session_id='session-a', query='', limit=10)
    observed = await asyncio.to_thread(provider.query, query)
    assert observed.ok and len(observed.records) == 1
    assert observed.records[0].value == 'captured value'
    assert observed.records[0].metadata['nested']['values'] == ['captured']


@pytest.mark.parametrize('scope', ['session_memory', 'profile_memory'])
async def test_sdk_memory_concurrent_extensions_keep_independent_captured_metadata(tmp_path, scope):
    providers = [SQLiteMemoryCapabilityProvider(tmp_path/'shared.sqlite3', extension_id=name)
                 for name in ('first-extension', 'second-extension')]
    key = 'topic' if scope == 'session_memory' else 'companion_setting.theme'
    requests = [MemoryWriteRequest(scope=scope, key=key, value=name, session_id='shared-session',
                                  metadata={'nested': {'values': [name]}}) for name in ('first', 'second')]
    with _held_storage(providers[0]) as first, _held_storage(providers[1]) as second:
        tasks = [asyncio.create_task(asyncio.to_thread(provider.write, request))
                 for provider, request in zip(providers, requests, strict=True)]
        try:
            assert all(await asyncio.gather(*(asyncio.to_thread(pair[0].wait, 10) for pair in (first, second))))
            for request in requests:
                request.metadata['nested']['values'].append('MUTATED')
        finally:
            first[1].set()
            second[1].set()
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [f"sqlite_code={getattr(result, 'sqlite_errorcode', None)} name={getattr(result, 'sqlite_errorname', None)}\n"
              + "".join(traceback.format_exception(result))
              for result in outcomes if isinstance(result, BaseException)]
    if errors:
        pytest.fail("\n".join(errors))
    assert all(result.ok for result in outcomes), outcomes
    query = MemoryQueryRequest(scope=scope, session_id='shared-session', query='', limit=10)
    for provider, value in zip(providers, ('first', 'second'), strict=True):
        result = await asyncio.to_thread(provider.query, query)
        assert result.ok and len(result.records) == 1
        assert result.records[0].value == value
        assert result.records[0].metadata['nested']['values'] == [value]
