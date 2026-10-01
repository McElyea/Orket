"""Isolated guarded native failure, actual SQLite exclusion and completion refusal."""
from __future__ import annotations

import asyncio
import hashlib
import sys
import threading
from pathlib import Path

import psutil
import pytest

import orket
from orket.adapters.execution import owned_io
from orket.adapters.tools import runtime
from orket.application.services import card_workspace_mutation_service
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging, settle_log_write_frontier
from orket.schema import CardStatus
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.guarded_mutation_controls import (
    assert_database_guard,
    assert_selected,
    competing_completion,
    fault_after_selected_guard_close,
    healthy_guarded_write,
    interrupt_guarded,
    invocation,
    prepare_guard,
)
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sdk_observation_controls import public_caller, read_records
from tests.helpers.tool_runtime_controls import entered


async def observe(root, route, kind, stop, monkeypatch):
    repo, completion, accepted, hold, failure, value = await prepare_guard(root, 'OSError' if route == 'close' else kind)
    closing = None
    if route == 'close':
        failure = OSError('native guard close acknowledgement failed') if kind == 'OSError' else SystemExit(73)
        failure.__cause__ = LookupError('original guard close failure cause')
        closing = fault_after_selected_guard_close(repo, failure, monkeypatch)
    operation, args, context = invocation(repo, hold, route, stop, root)
    graph = (failure.__cause__, failure.__context__, failure.__suppress_context__) if failure else None
    active = asyncio.create_task(public_caller(operation))
    contender = None
    observations = []
    try:
        await entered(hold)
        count = await interrupt_guarded(active, stop, hold.authority_task)
        await asyncio.to_thread(assert_database_guard, repo.db_path)
        contender = asyncio.create_task(public_caller(competing_completion(repo, completion, accepted.request)))
        assert await sqlite_response(root / 'responsive.sqlite3',
            lambda key, item: observations.append({'name': key, 'value': item})) < .5
        await asyncio.wait({active, contender}, timeout=.02)
        before = {'route': route, 'kind': kind, 'stop': stop, 'invoke_pending': not active.done(),
            'competitor_pending': not contender.done(), 'native_finished': hold.finished.is_set(),
            'caller_cancel_requests': count, 'authority_cancel_requests': hold.authority_task.cancelling(),
            'database_guard_held': True, 'native_calls': hold.calls}
        await asyncio.to_thread(write_payload_with_diff_ledger, root / 'guard-before-release.json', before)
        hold.release.set()
        outcome, refused = await asyncio.wait_for(asyncio.gather(active, contender), 10)
        await owned_io.run_owned_thread(settle_log_write_frontier, label='fixture-guarded-log-frontier')
        records = await read_records(root / 'orket.log')
        timeouts = [row for row in records if row['event'] == 'tool_timeout']
        after = {**before, 'native_finished': hold.finished.is_set(), 'outcome_type': type(outcome).__name__,
            'completion_type': type(refused).__name__, 'timeout_records': len(timeouts)}
        await asyncio.to_thread(write_payload_with_diff_ledger, root / 'guard-after-settlement.json', after)
        assert before['invoke_pending'] and before['competitor_pending'] and not before['native_finished']
        assert hold.finished.is_set() and not hold.expired and hold.calls == 1
        assert hold.worker != threading.get_ident() and hold.args is args
        assert hold.context is context if route == 'mutation' else hold.context is not context
        assert hold.context['nested'] is context['nested']
        assert await asyncio.to_thread((root / 'agent_output/tool-effect.bin').read_bytes) == b'real tool effect'
        assert isinstance(refused, CardCompletionRejected)
        assert 'ACCEPTANCE_REQUIRED' in str(refused)
        assert (await repo.get_by_id('card')).status == CardStatus.CODE_REVIEW
        assert await repo.get_card_history('card') == []
        assert_selected(outcome, failure, value, 'tool' if route == 'close' else route, kind, stop)
        if closing is not None:
            assert closing.closed and closing.calls == 1 and closing.worker != threading.get_ident()
            assert failure.__context__ is hold.failure and failure.__cause__ is graph[0]
        elif failure is not None:
            assert (failure.__cause__, failure.__context__, failure.__suppress_context__) == graph
        assert len(timeouts) == int(route == 'tool' and stop == 'deadline' and kind == 'success')
        return {**after, 'outcome_policy': True, 'real_completion_refused': True,
            'native_graph_preserved': True, 'healthy_followup': await healthy_guarded_write(repo, root),
            'observations': observations, 'task_settled_before_emergency': active.done() and contender.done()}
    finally:
        hold.release.set()
        tasks = [active] + ([contender] if contender is not None else [])
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
        finally:
            if hold.entered.is_set():
                assert await asyncio.to_thread(hold.finished.wait, 3), 'native fixture did not settle'


async def exercise(root, route, kind, stop):
    prepared = await prepare_logging(LoggingInputs(root, timezone_name='MST'))
    with bind_logging(prepared), pytest.MonkeyPatch.context() as monkeypatch:
        if route == 'diagnostic':
            from tests.helpers.guarded_mutation_diagnostic import observe_diagnostic
            return await observe_diagnostic(root, kind)
        if route == 'refusal':
            from tests.helpers.guarded_mutation_controls import observe_refusal
            return await observe_refusal(root, kind)
        if route == 'custom':
            from tests.helpers.guarded_mutation_controls import observe_forwarding
            return await observe_forwarding(root, stop)
        return await observe(root, route, kind, stop, monkeypatch)


def main():
    root = Path(sys.argv[1]).resolve()
    result = asyncio.run(exercise(root, *sys.argv[2:]))
    process = psutil.Process()
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
        owner_origin=str(Path(owned_io.__file__).resolve()),
        owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        process_identity={'pid': process.pid, 'create_time': process.create_time()},
        product_sources={name: {'path': str(Path(module.__file__).resolve()),
            'sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
            for name, module in [('runtime', runtime), ('mutation', card_workspace_mutation_service)]})
    write_payload_with_diff_ledger(root / 'result.json', result)


if __name__ == '__main__':
    main()
