"""Actual completion evidence, native writes and interruption controls for guarded tools."""
from __future__ import annotations

import asyncio
import sqlite3
import time
from functools import partial

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.tools.runtime import ToolRuntimeExecutor
from orket.application.services.card_workspace_mutation_service import CardWorkspaceMutationService
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus
from tests.helpers.card_completion import completion_components, text_acceptance
from tests.helpers.tool_runtime_controls import NativeToolHold, tool_failure


async def prepare_guard(root, kind):
    effect_root = root / 'agent_output'
    await asyncio.to_thread(effect_root.mkdir, parents=True, exist_ok=True)
    source = effect_root / 'tool-effect.bin'
    await asyncio.to_thread(source.write_bytes, b'accepted before mutation')
    repo, completion = completion_components(root / 'cards.sqlite3', root)
    definition = text_acceptance(source.relative_to(root).as_posix(), 'accepted before mutation', workload_id='guarded-native')
    await repo.save(IssueRecord(id='card', summary='Guard native mutation', seat='developer',
        status=CardStatus.CODE_REVIEW, params={'completion_acceptance': definition.model_dump(mode='json')}))
    context = await completion.begin_attempt(repo, card_id='card', run_id='run', attempt_id='attempt')
    result = await completion.evaluate_attempt(repo, context)
    assert result.decision.sufficient
    failure = tool_failure(kind)
    value = BaseException('guarded returned exception value') if kind == 'returned-exception' else 37
    hold = NativeToolHold(effect_root, failure, value)
    return repo, completion, result, hold, failure, value


def invocation(repo, hold, route, stop, root):
    authority = CardWorkspaceMutationService(repo)
    admitted_run = authority.run
    hold.authority_task = None

    async def observe_authority(operation):
        hold.authority_task = asyncio.current_task()
        return await admitted_run(operation)

    authority.run = observe_authority
    args, context = {'content': b'real tool effect'}, {'nested': {'value': 'borrowed'}}

    async def native_write():
        result, = await run_owned_thread(lambda: (hold.run(args, context=context),), label='fixture-guarded-write')
        return result

    if route == 'mutation':
        return authority.run(native_write), args, context
    return ToolRuntimeExecutor().invoke(hold.run, args, context=context, workspace=root, tool_name='guarded_write',
        tool_timeout_seconds=.05 if stop.startswith('deadline') else 10, mutation_authority=authority), args, context


async def interrupt_guarded(active, stop, authority_task):
    if stop.startswith('deadline'):
        started = time.perf_counter()
        assert authority_task is not None, 'the admitted authority did not record its task'
        while authority_task.cancelling() == 0 and not active.done() and time.perf_counter() - started < 2:
            await asyncio.wait({active}, timeout=.005)
        assert authority_task.cancelling() == 1, 'the tool deadline did not interrupt the admitted authority'
    if stop in {'cancel', 'deadline-repeated'}:
        active.cancel('first explicit guarded interruption')
        await asyncio.sleep(0)
        active.cancel('repeated explicit guarded interruption')
    return active.cancelling()


def assert_database_guard(database):
    with sqlite3.connect(database, timeout=0) as connection:
        try:
            connection.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as failure:
            assert str(failure) == 'database is locked'
        else:
            connection.rollback()
            raise AssertionError('native database writer guard was released before effect acknowledgement')
    return True


def competing_completion(repo, completion, request):
    competitor = AsyncCardRepository(repo.db_path, completion_authority=completion)
    return competitor.update_status('card', CardStatus.DONE, completion_request=request)


def assert_selected(outcome, failure, value, route, kind, stop):
    if kind == 'returned-exception':
        assert outcome is value  # Preserve the existing guarded failure-value policy.
    elif failure is not None:
        if route == 'tool' and isinstance(failure, OSError):
            assert outcome == {'ok': False, 'error': str(failure)}
        else:
            assert outcome is failure
    elif stop == 'deadline':
        assert outcome == {'ok': False, 'error': 'tool_timeout', 'tool': 'guarded_write'}
    elif stop != 'none':
        assert type(outcome) is asyncio.CancelledError
    elif route == 'mutation':
        assert outcome is value
    else:
        assert outcome == {'ok': True, 'result': value}
    return True


async def healthy_guarded_write(repo, root):
    path = root / 'following-guarded-effect.bin'
    result = await CardWorkspaceMutationService(repo).run(
        partial(run_owned_thread, partial(path.write_bytes, b'following effect'), label='fixture-following-write'))
    assert result == len(b'following effect')
    assert await asyncio.to_thread(path.read_bytes) == b'following effect'
    return True


class ForwardingAuthority:
    """Explicit custom protocol control: await the admitted operation in this same task."""

    def __init__(self):
        self.calls = 0
        self.task = None

    async def run(self, operation):
        self.task = asyncio.current_task()
        self.calls += 1
        return await operation()


async def observe_forwarding(root, stop):
    from tests.helpers.runtime_verification_hold import sqlite_response
    from tests.helpers.sdk_observation_controls import public_caller
    from tests.helpers.tool_runtime_controls import AsyncToolHold, entered

    hold = AsyncToolHold(root, 37)
    authority = ForwardingAuthority()
    operation = ToolRuntimeExecutor().invoke(hold.run, {'content': b'real tool effect'}, workspace=root,
        mutation_authority=authority, tool_name='custom_guarded',
        tool_timeout_seconds=.05 if stop.startswith('deadline') else 10)
    active = asyncio.create_task(public_caller(operation))
    try:
        await entered(hold)
        count = await interrupt_guarded(active, stop, authority.task)
        await asyncio.wait_for(hold.cleanup_entered.wait(), 3)
        assert not active.done() and not hold.finished.is_set()
        assert await sqlite_response(root / 'custom-responsive.sqlite3', lambda *_args: None) < .5
        assert len(hold.cancellations) == 1
        hold.release.set()
        outcome = await asyncio.wait_for(active, 10)
        assert type(outcome) is asyncio.CancelledError
        assert len(hold.cancellations) == 1 and hold.finished.is_set() and authority.calls == 1
        assert await asyncio.to_thread((root / 'tool-effect.bin').read_bytes) == b'real tool effect'
        return {'route': 'custom', 'stop': stop, 'one_authority_admission': True,
            'one_forwarded_cancellation': True, 'cleanup_settled': True, 'caller_cancel_requests': count,
            'authority_cancel_requests': authority.task.cancelling(),
            'task_settled_before_emergency': active.done()}
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(active, return_exceptions=True), 10)
        if hold.task is not None:
            await asyncio.wait_for(asyncio.gather(hold.task, return_exceptions=True), 3)


def fault_after_selected_guard_close(repo, failure, monkeypatch):
    """Delegate real SQLite close, then refuse only the selected guard's acknowledgement."""
    import threading
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    import aiosqlite

    state = SimpleNamespace(connections=[], closed=False, calls=0, worker=None)
    actual_connection, actual_close = repo._connection, aiosqlite.Connection.close

    @asynccontextmanager
    async def connection(**options):
        async with actual_connection(**options) as admitted:
            state.connections.append(admitted)
            yield admitted

    async def close(admitted):
        await actual_close(admitted)
        if not state.connections or admitted is not state.connections[0]:
            return
        try:
            _transaction = admitted.in_transaction
        except ValueError:
            state.closed = True
        else:
            raise AssertionError('actual SQLite connection remained open')

        def refuse_acknowledgement():
            state.calls += 1
            state.worker = threading.get_ident()
            raise failure

        await run_owned_thread(refuse_acknowledgement, label='fixture-guard-close-acknowledgement')

    monkeypatch.setattr(repo, '_connection', connection)
    monkeypatch.setattr(aiosqlite.Connection, 'close', close)
    return state


async def observe_refusal(root, kind):
    from tests.helpers.tool_runtime_controls import entered

    hold = NativeToolHold(root, None, 37)
    future = asyncio.get_running_loop().create_future()
    invoked = []

    async def existing_work():
        result = await run_owned_thread(lambda: hold.run({'content': b'real tool effect'}, context={}),
                                       label='fixture-existing-caller-work')
        future.set_result(result)
        return result

    class InvalidAuthority:
        def run(self, _operation):
            return selected

    def forbidden_tool(_args, *, context):
        invoked.append(context)
        raise AssertionError('invalid authority admission invoked the tool')

    existing = asyncio.create_task(existing_work())
    selected = existing if kind == 'task' else future
    try:
        await entered(hold)
        result = await ToolRuntimeExecutor().invoke(forbidden_tool, {}, mutation_authority=InvalidAuthority())
        assert result['ok'] is False and isinstance(result['error'], str) and result['error']
        assert not invoked and not selected.done() and not existing.done() and not hold.finished.is_set()
        assert not selected.cancelled() and not existing.cancelled()
        hold.release.set()
        assert await asyncio.wait_for(existing, 10) == 37
        assert await future == 37 and hold.finished.is_set() and not hold.expired
        assert await asyncio.to_thread((root / 'tool-effect.bin').read_bytes) == b'real tool effect'
        return {'route': 'refusal', 'kind': kind, 'rejected_without_adoption': True,
                'actual_caller_work_retained': True, 'forbidden_tool_calls': len(invoked)}
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(existing, return_exceptions=True), 10)
        if hold.entered.is_set():
            assert await asyncio.to_thread(hold.finished.wait, 3)
