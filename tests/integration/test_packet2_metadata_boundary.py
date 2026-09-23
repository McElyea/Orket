"""Layer: integration. Actual packet-2 receipt discovery and artifact audit responsiveness."""
import asyncio
import json
import os
import threading
import time
from pathlib import Path

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.core.domain.records import IssueRecord
from orket.runtime.execution.phase_c_runtime_truth import collect_phase_c_packet2_facts

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_metadata(monkeypatch, target, method, enabled, start_probe):
    owner = os if method == 'scandir' else Path
    original = getattr(owner, method)
    entered, release = threading.Event(), threading.Event()
    threads, timers = [], []

    def observe(path, *args, **options):
        if not isinstance(path, int) and Path(path) == target and not entered.is_set():
            entered.set()
            threads.append(threading.get_ident())
            start_probe()
            if enabled:
                timer = threading.Timer(.75, release.set)
                timers.append(timer)
                timer.start()
                assert release.wait(5), 'Packet-2 metadata fixture was not released'
        return original(path, *args, **options)

    monkeypatch.setattr(owner, method, observe)
    return entered, release, threads, timers


@pytest.mark.parametrize('site', ['root', 'discovery', 'artifact'])
@pytest.mark.parametrize('held', [False, True], ids=['healthy', 'native-hold'])
async def test_packet2_metadata_preserves_sqlite_response(tmp_path, monkeypatch, record_property, site, held):
    workspace = tmp_path / 'workspace'
    root = workspace / 'observability/run'
    receipt = root / 'ISSUE/001_coder/protocol_receipts.log'
    artifact = workspace / 'agent_output/result.txt'
    await asyncio.to_thread(receipt.parent.mkdir, parents=True)
    await asyncio.to_thread(artifact.parent.mkdir, parents=True)
    await asyncio.to_thread(artifact.write_text, 'actual output', encoding='utf-8')
    row = {'tool': 'write_file', 'operation_id': 'fixture-write', 'receipt_seq': 1,
           'tool_args': {'path': 'agent_output/result.txt'}, 'execution_result': {'ok': True, 'path': 'agent_output/result.txt'}}
    await asyncio.to_thread(receipt.write_text, json.dumps(row) + '\n', encoding='utf-8')
    target, method = (artifact, 'exists') if site == 'artifact' else (root, 'scandir' if site == 'discovery' else 'exists')
    ready, starts, loop = asyncio.Event(), [], asyncio.get_running_loop()

    def start_probe():
        starts.append(time.perf_counter())
        loop.call_soon_threadsafe(ready.set)

    entered, release, threads, timers = hold_metadata(monkeypatch, target, method, held, start_probe)
    cards = AsyncCardRepository(tmp_path / 'cards.sqlite3')

    async def sqlite():
        await ready.wait()
        independent = AsyncCardRepository(tmp_path / 'response.sqlite3')
        await independent.save(IssueRecord(id='metadata', seat='fixture', summary='Packet-2 concurrency'))
        assert (await independent.get_by_id('metadata')).id == 'metadata'
        return time.perf_counter() - starts[0]

    task = asyncio.create_task(collect_phase_c_packet2_facts(workspace=workspace, run_id='run', cards_repo=cards))
    probe = asyncio.create_task(sqlite())
    try:
        result, elapsed = await asyncio.wait_for(asyncio.gather(task, probe), 5)
        record_property('responsive_sqlite_seconds', elapsed)
        if held:
            assert entered.is_set() and threads == [threads[0]] and threads[0] != threading.get_ident()
        assert elapsed < .5
        audit = result['narration_to_effect_audit']
        assert audit['verified_count'] == 1 and audit['missing_effect_count'] == 0
        assert audit['entries'][0]['operation_id'] == 'fixture-write'
        assert json.loads(await asyncio.to_thread(receipt.read_text, encoding='utf-8')) == row
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, probe, return_exceptions=True), 5)
        for timer in timers:
            await asyncio.to_thread(timer.join, 5)
