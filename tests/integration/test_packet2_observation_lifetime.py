"""Layer: integration. Native packet-2 discovery, reads and audit settle before return."""
import asyncio
import os
import threading
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.runtime.execution.phase_c_runtime_truth import collect_phase_c_packet2_facts
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_async_file_native_lifetime import hold_native_open, observe_native_operation
from tests.integration.test_direct_metadata_lifetime import held_metadata
from tests.integration.test_packet2_capture_lifetime import packet_files
from tests.integration.test_packet2_receipt_parity import write_legacy_turn

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class ObservedScan:
    """Track physical directory iterator closure independently of the caller task."""

    def __init__(self, inner):
        self.inner, self.closed = inner, False

    def __enter__(self):
        self.inner.__enter__()
        return self

    def __exit__(self, *error):
        try:
            return self.inner.__exit__(*error)
        finally:
            self.closed = True

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.inner)

    def close(self):
        self.inner.close()
        self.closed = True


def hold_scan(monkeypatch, target, state):
    original = os.scandir

    def observed(path):
        iterator = original(path)
        if isinstance(path, int) or Path(path) != target or state.entered.is_set():
            return iterator
        stream = ObservedScan(iterator)
        state.streams.append(stream)
        state.entered.set()
        try:
            assert state.release.wait(5), 'Directory iterator fixture was not released'
            return stream
        except BaseException:
            stream.close()
            raise
        finally:
            state.finished.set()

    monkeypatch.setattr(os, 'scandir', observed)


@pytest.mark.parametrize('site', ['protocol-scan', 'legacy-scan', 'legacy-calls', 'legacy-result'])
@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_packet2_owns_discovery_and_legacy_handles(tmp_path, monkeypatch, record_property, site, stop):
    workspace = tmp_path / 'workspace'
    directory, result = await asyncio.to_thread(write_legacy_turn, workspace)
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[])
    if site == 'protocol-scan':
        hold_scan(monkeypatch, workspace / 'observability/run', state)
    elif site == 'legacy-scan':
        state = held_metadata(monkeypatch, workspace / 'observability/run', 'iterdir', False)
        state.streams = []
    else:
        target = directory / 'parsed_tool_calls.json' if site == 'legacy-calls' else result
        hold_native_open(monkeypatch, target, state, failure=False)
    operation = partial(collect_phase_c_packet2_facts, workspace=workspace, run_id='run',
                        cards_repo=AsyncCardRepository(tmp_path / 'cards.sqlite3'))
    await observe_native_operation(SimpleNamespace(invoke=operation), 'invoke', [], tmp_path, state, stop, 'adapter', record_property)


@pytest.mark.parametrize('site', ['root', 'audit-resolve', 'audit-exists', 'audit-is-file'])
@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_packet2_owns_metadata_and_stops_later_stages(tmp_path, monkeypatch, record_property, site, stop):
    workspace = tmp_path / 'workspace'
    await packet_files(workspace, 'fixture-write')
    root, artifact = workspace / 'observability/run', workspace / 'agent_output/result.txt'
    target, method = {'root': (root, 'exists'), 'audit-resolve': (artifact, 'resolve'),
                      'audit-exists': (artifact, 'exists'), 'audit-is-file': (artifact, 'is_file')}[site]
    state = held_metadata(monkeypatch, target, method, False)
    state.streams = []
    original_exists, source_admitted = Path.exists, []

    def observed_source(path):
        if path == workspace / 'agent_output/source_attribution_receipt.json':
            source_admitted.append(True)
        return original_exists(path)

    monkeypatch.setattr(Path, 'exists', observed_source)
    operation = partial(collect_phase_c_packet2_facts, workspace=workspace, run_id='run',
                        cards_repo=AsyncCardRepository(tmp_path / 'cards.sqlite3'))
    await observe_native_operation(SimpleNamespace(invoke=operation), 'invoke', [], tmp_path, state, stop, 'adapter', record_property)
    assert not source_admitted
    assert await asyncio.to_thread(artifact.read_text, encoding='utf-8') == 'fixture-write'


@pytest.mark.parametrize('site', ['root', 'artifact'])
async def test_packet2_drain_failure_is_not_clean_cancellation(tmp_path, monkeypatch, record_property, site):
    workspace = tmp_path / 'workspace'
    await packet_files(workspace, 'fixture-write')
    target = workspace / ('observability/run' if site == 'root' else 'agent_output/result.txt')
    state = held_metadata(monkeypatch, target, 'exists', True)
    task = asyncio.create_task(collect_phase_c_packet2_facts(workspace=workspace, run_id='run',
        cards_repo=AsyncCardRepository(tmp_path / 'cards.sqlite3')))
    timer = threading.Timer(.8, state.release.set)
    timer.start()
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        assert state.threads[0] != threading.get_ident()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(.03)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        with pytest.raises(OSError, match='controlled native metadata failure'):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set()
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert state.finished.is_set() and not timer.is_alive()
