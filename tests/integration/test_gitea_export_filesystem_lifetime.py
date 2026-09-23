"""Layer: integration. Owned export filesystem effects and actual SQLite response."""
import asyncio
import shutil
import threading
from pathlib import Path

import pytest

from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_gitea_export_native_ownership import exporter, run_values
from tests.integration.test_gitea_http_ownership import interrupt
from tests.integration.test_short_http_ownership import clean_network

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_effect(monkeypatch, selected, name, accepts, *, fail):
    original = getattr(selected, name)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    workers = []

    def held(*args, **options):
        if not accepts(*args) or entered.is_set():
            return original(*args, **options)
        workers.append(threading.get_ident())
        entered.set()
        try:
            assert release.wait(.8), 'Filesystem effect blocked or escaped its owner'
            result = original(*args, **options)
            if fail:
                raise OSError('controlled failure after actual filesystem effect')
            return result
        finally:
            finished.set()

    monkeypatch.setattr(selected, name, held)
    return entered, release, finished, workers


@pytest.mark.parametrize('effect', ['mkdir', 'resolve', 'remove', 'copy'])
@pytest.mark.parametrize('mode', ['repeated', 'timeout', 'failure'])
async def test_export_cache_work_retained(tmp_path, monkeypatch, record_property, effect, mode):
    clean_network(monkeypatch)
    owner = await exporter(tmp_path)
    git = owner._transport('filesystem')
    payload, target = tmp_path / 'payload', git.repo_dir / 'runs/fixture'

    def setup():
        payload.mkdir()
        (payload / 'manifest.json').write_text('captured', encoding='utf-8')
        if effect != 'mkdir':
            target.mkdir(parents=True)
            (target / 'old.txt').write_text('old', encoding='utf-8')

    await asyncio.to_thread(setup)
    hooks = {'mkdir': (Path, 'mkdir', lambda p, *args: p == git.repo_dir),
             'resolve': (Path, 'resolve', lambda p, *args: p == git.repo_dir),
             'remove': (shutil, 'rmtree', lambda p, *args: p == target),
             'copy': (shutil, 'copytree', lambda p, *args: p == payload)}
    entered, release, finished, workers = hold_effect(monkeypatch, *hooks[effect], fail=mode == 'failure')
    deadline = asyncio.timeout(None)

    async def operation():
        async with deadline:
            return await (git.initialize() if effect == 'mkdir' else git.prepare(payload, 'runs/fixture', None))

    task = asyncio.create_task(operation())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        await interrupt(task, 'repeated' if mode == 'failure' else mode, deadline)
        assert not finished.is_set() and workers == [workers[0]] and workers[0] != threading.get_ident()
        release.set()
        expected = OSError if mode == 'failure' else TimeoutError if mode == 'timeout' else asyncio.CancelledError
        with pytest.raises(expected):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert finished.is_set()
        assert not await asyncio.to_thread((git.repo_dir / '.git').exists)
        if effect == 'copy':
            assert await asyncio.to_thread((target / 'manifest.json').read_text, encoding='utf-8') == 'captured'
        if effect == 'remove':
            assert not await asyncio.to_thread((target / 'old.txt').exists)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_export_payload_failure_precedes_cancellation(tmp_path, monkeypatch, record_property):
    clean_network(monkeypatch)
    owner = await exporter(tmp_path)
    entered, release, finished, workers = hold_effect(
        monkeypatch, owner, '_build_payload', lambda *args: True, fail=True)
    task = asyncio.create_task(owner.prepare_export(**run_values({'captured': True})))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        task.cancel()
        await asyncio.sleep(.01)
        assert not task.done() and workers[0] != threading.get_ident()
        release.set()
        with pytest.raises(OSError, match='after actual filesystem effect'):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert finished.is_set()
        assert not await asyncio.to_thread((tmp_path / 'cache/repo_cache').exists)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize('run_path', ['../escape', '.'])
async def test_export_copy_refuses_path_escape(tmp_path, monkeypatch, run_path):
    clean_network(monkeypatch)
    git = (await exporter(tmp_path))._transport('containment')
    with pytest.raises(ValueError, match='E_GITEA_EXPORT_PATH_ESCAPE'):
        await git.prepare(tmp_path / 'absent', run_path, None)
    assert not await asyncio.to_thread(git.repo_dir.exists)
