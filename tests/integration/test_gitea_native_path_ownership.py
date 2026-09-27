"""Layer: integration. Native path observation is retained before Git command admission."""
import asyncio
import json
import os
import threading
from pathlib import Path

import pytest

import orket.adapters.vcs.gitea_export_git as transport
import orket.adapters.vcs.gitea_git_paths as paths
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_gitea_git_repository_boundary import _fixture
from tests.integration.test_gitea_http_ownership import interrupt

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _held_query(monkeypatch, *, fail):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    workers = []
    original = paths._short_path if os.name == 'nt' else lambda path: path

    def held(path):
        if entered.is_set():
            return original(path)
        workers.append(threading.get_ident())
        entered.set()
        try:
            assert release.wait(.8), 'Native path observation escaped its owner'
            observed = original(path)
            if fail:
                raise OSError('controlled native path observation failure')
            return observed
        finally:
            finished.set()

    monkeypatch.setattr(paths, '_short_path', held)
    # POSIX has no Windows name API: exercise the same owner/validation with its
    # real directory spelling; the four boundary tests retain ordinary POSIX Git.
    if os.name != 'nt':
        monkeypatch.setattr(transport, 'needs_native_repository_paths', lambda root: True)
    return entered, release, finished, workers


async def _context(tmp_path_factory):
    root = Path(await asyncio.to_thread(tmp_path_factory.mktemp, 'gp'))
    target, _, _, environment = await asyncio.to_thread(_fixture, root, 255)
    if os.name != 'nt':
        target = root / 'repo'
    owner = CommandProcessSupervisor(target, cancellation_event='gitea_native_path_interrupted')
    git = transport.GiteaExportGit(target, 'http://127.0.0.1:1/fixture.git', environment, command_runner=owner)
    await git.initialize()
    calls = []

    class ObservedRunner:
        async def run(self, arguments, **options):
            calls.append((arguments, options))
            return await owner.run(arguments, **options)

    git._command_runner = ObservedRunner()
    return root, target, git, calls


@pytest.mark.parametrize('mode', ['complete', 'repeated', 'timeout', 'native-failure'])
async def test_native_path_observation_retains_worker_and_command_inputs(
    tmp_path_factory, monkeypatch, record_property, mode,
):
    root, target, git, calls = await _context(tmp_path_factory)
    git.environment['TEMP'] = str(root / 'captured')
    entered, release, finished, workers = _held_query(monkeypatch, fail=mode == 'native-failure')
    deadline = asyncio.timeout(None)

    async def operation():
        async with deadline:
            return await git.command('rev-parse', '--git-dir')

    task = asyncio.create_task(operation())
    elapsed = []
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await responsive_sqlite(root / 'responsive.sqlite3', lambda key, value: (
            elapsed.append(value), record_property(key, value)))
        assert len(elapsed) == 1 and 0 < elapsed[0] < .5
        git.environment['TEMP'], git.repo_dir, git._command_runner = 'late-input', root / 'late-root', None
        if mode != 'complete':
            await interrupt(task, 'repeated' if mode == 'native-failure' else mode, deadline)
        assert not task.done() and not finished.is_set() and not calls
        assert len(workers) == 1 and workers[0] != threading.get_ident()
        release.set()
        if mode == 'complete':
            assert (await asyncio.wait_for(asyncio.shield(task), 5))[0] == 0
            assert len(calls) == 1 and calls[0][1]['cwd'] == target
            assert calls[0][1]['environment']['TEMP'] == str(root / 'captured')
        else:
            expected = RuntimeError if mode == 'native-failure' else TimeoutError if mode == 'timeout' else asyncio.CancelledError
            with pytest.raises(expected) as observed:
                await asyncio.wait_for(asyncio.shield(task), 5)
            if mode == 'native-failure':
                assert str(observed.value) == 'E_GITEA_GIT_NATIVE_PATH_UNAVAILABLE'
                assert isinstance(observed.value.__cause__, OSError)
            assert not calls
        assert finished.is_set()
        record_property('gitea_native_path_lifetime', json.dumps(dict(mode=mode, worker=workers[0],
            loop=threading.get_ident(), settled=finished.is_set(), command_count=len(calls),
            sqlite_path=str(root / 'responsive.sqlite3'), sqlite_seconds=elapsed[0],
            path='native-windows' if os.name == 'nt' else 'controlled-posix-spelling'), sort_keys=True))
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
