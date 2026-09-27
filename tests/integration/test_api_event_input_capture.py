"""Layer: integration. API event capture rejects hooks before real publication."""
from __future__ import annotations

import asyncio
import json
import logging
import threading

import pytest

from orket import logging as event_adapter
from orket.adapters.observability import log_publication as logging_owner
from orket.application.services.api_event_service import ApiEventService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ERROR = "E_LOG_EVENT_INPUT_UNSUPPORTED"


def _sentinels(calls):
    class HookMeta(type):
        def __hash__(cls):
            calls.append('metaclass-hash')
            return id(cls)

        def __eq__(cls, other):
            calls.append('metaclass-equality')
            return False

    class Hooks(metaclass=HookMeta):
        def __deepcopy__(self, memo):
            calls.append('deepcopy')
            return self

        def __str__(self):
            calls.append('str')
            return 'unsafe-hook-value'

        def __repr__(self):
            calls.append('repr')
            return 'unsafe-hook-value'

        def __bool__(self):
            calls.append('bool')
            return True

        def __int__(self):
            calls.append('int')
            return 1

    class HookDict(dict):
        def __deepcopy__(self, memo):
            calls.append('mapping-deepcopy')
            return dict(self)

    class HookList(list):
        def __deepcopy__(self, memo):
            calls.append('list-deepcopy')
            return list(self)

    class HookString(str):
        def __deepcopy__(self, memo):
            calls.append('string-deepcopy')
            return str(self)

    return Hooks, HookDict, HookList, HookString


def _unsupported(kind, calls):
    Hooks, HookDict, HookList, HookString = _sentinels(calls)
    event, payload = 'api_capture_refusal', {'safe': 1}
    if kind == 'opaque':
        payload['nested'] = [Hooks()]
    elif kind == 'mapping-subclass':
        payload = HookDict(safe=1)
    elif kind == 'list-subclass':
        payload['nested'] = HookList([1])
    elif kind == 'string-subclass':
        payload['nested'] = HookString('unsafe')
    elif kind == 'key-subclass':
        payload = {HookString('unsafe'): 1}
    elif kind == 'nonstring-key':
        payload = {1: 'unsafe'}
    elif kind == 'cycle-dict':
        payload['self'] = payload
    elif kind == 'cycle-list':
        items = []
        items.append(items)
        payload['nested'] = items
    elif kind == 'nan':
        payload['nested'] = float('nan')
    elif kind == 'infinity':
        payload['nested'] = float('inf')
    elif kind == 'root-list':
        payload = []
    elif kind == 'event-subclass':
        event = HookString('api_capture_refusal')
    elif kind == 'event-object':
        event = Hooks()
    else:
        raise AssertionError(kind)
    return event, payload


@pytest.mark.parametrize('kind', [
    'opaque', 'mapping-subclass', 'list-subclass', 'string-subclass', 'key-subclass',
    'nonstring-key', 'cycle-dict', 'cycle-list', 'nan', 'infinity', 'root-list',
    'event-subclass', 'event-object',
])
async def test_unsupported_api_event_refuses_before_hooks_and_publication(tmp_path, record_property, kind):
    calls, handlers, subscribers = [], [], []
    event, payload = _unsupported(kind, calls)

    class Observe(logging.Handler):
        def emit(self, record):
            handlers.append(record.name)

    handler, logger = Observe(), logging.getLogger('orket')
    callback = subscribers.append
    logger.addHandler(handler)
    event_adapter.subscribe_to_events(callback)
    error = None
    try:
        try:
            await ApiEventService(tmp_path).emit(event, payload)
        except (TypeError, ValueError, RecursionError) as observed:
            error = observed
    finally:
        event_adapter.unsubscribe_from_events(callback)
        logger.removeHandler(handler)
        handler.close()
    files = await asyncio.to_thread(lambda: sorted(path.name for path in tmp_path.iterdir()))
    record_property('api_event_capture_refusal', json.dumps(dict(
        kind=kind, error_type=None if error is None else type(error).__name__,
        error_message=None if error is None else str(error), hooks=calls,
        handler_count=len(handlers), subscriber_count=len(subscribers), files=files), sort_keys=True))
    assert type(error) is TypeError and str(error) == ERROR
    assert calls == [] and handlers == [] and subscribers == [] and files == []


async def test_api_event_keeps_plain_nested_values_after_capture(tmp_path, monkeypatch, record_property):
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = logging_owner._append_line_sync
    invocations = []

    def held_write(path, line):
        invocations.append((str(path), threading.get_ident()))
        entered.set()
        try:
            assert release.wait(5), 'Fixture release missing'
            original(path, line)
        finally:
            settled.set()

    monkeypatch.setattr(logging_owner, '_append_line_sync', held_write)
    shared = {'values': [None, True, False, 7, -2, 1.5, 'captured']}
    payload = {'nested': shared, 'alias': shared, 'tuple': ('a', {'b': [2]})}
    owner = asyncio.create_task(ApiEventService(tmp_path).emit('api_capture_plain', payload))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        shared['values'].append('late')
        payload['tuple'][1]['b'].append(3)
        release.set()
        await asyncio.wait_for(owner, 3)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(owner, return_exceptions=True), 3)
    assert settled.is_set() and len(invocations) == 1
    assert invocations[0][1] != threading.get_ident()
    path = tmp_path / 'orket.log'
    record = json.loads(await asyncio.to_thread(path.read_text, encoding='utf-8'))
    assert record['data']['nested'] == record['data']['alias'] == {
        'values': [None, True, False, 7, -2, 1.5, 'captured']}
    assert record['data']['tuple'] == ['a', {'b': [2]}]
    record_property('api_event_capture_plain', json.dumps(dict(
        path=str(path), file_record=record, worker=invocations[0][1], loop=threading.get_ident(),
        attempts=len(invocations), settled=settled.is_set()), sort_keys=True))
