"""Layer: integration. Actual Git subprocess boundaries and captured raw inputs."""
import asyncio
import os

import psutil
import pytest

from orket.adapters.vcs.gitea_export_git import GiteaExportGit
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_gitea_export_native_ownership import exporter, fixture_alias
from tests.integration.test_short_http_ownership import clean_network

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('kind', ['stdout-bound', 'stdout-over', 'stderr-bound', 'stderr-over', 'nonzero', 'invalid-utf8'])
async def test_export_git_output_contract(tmp_path, monkeypatch, kind):
    clean_network(monkeypatch)
    git = (await exporter(tmp_path))._transport('output')
    await git.initialize()
    stream = 'stderr' if kind.startswith('stderr') else 'stdout'
    count = 262145 if kind.endswith('over') else 262144
    code = ("import sys\nsys.exit(7)\n" if kind == 'nonzero' else
            "import sys\nsys.stdout.buffer.write(bytes([255]))\n" if kind == 'invalid-utf8' else
            f"import sys\nsys.{stream}.buffer.write(b'x'*{count})\n")
    command = await fixture_alias(tmp_path, 'output', code)
    args = ('-c', 'alias.output-proof=' + command, 'output-proof')
    if kind.endswith('over'):
        with pytest.raises(RuntimeError, match='E_GITEA_GIT_COMMAND_FAILED'):
            await git.command(*args)
    elif kind == 'invalid-utf8':
        with pytest.raises(UnicodeDecodeError):
            await git.command(*args)
    else:
        code, observed = await git.command(*args, allowed=(0, 7))
        assert code == (7 if kind == 'nonzero' else 0)
        assert observed == ('x' * count if stream == 'stdout' and kind != 'nonzero' else '')
        if kind == 'nonzero':
            with pytest.raises(RuntimeError, match='E_GITEA_GIT_COMMAND_FAILED:-c:7'):
                await git.command(*args)


@pytest.mark.parametrize('mutate', [False, True])
async def test_raw_export_git_copies_environment(tmp_path, monkeypatch, mutate):
    clean_network(monkeypatch)
    owner = await exporter(tmp_path)
    original = owner._transport('raw-inputs')
    values = dict(original.environment, GIT_AUTHOR_NAME='captured-author')
    git = GiteaExportGit(original.repo_dir, original.repo_url, values, command_runner=owner._command_runner)
    if mutate:
        values['GIT_AUTHOR_NAME'] = 'changed-author'
    await git.initialize()
    assert (await git.command('var', 'GIT_AUTHOR_IDENT'))[1].startswith('captured-author <')


@pytest.mark.parametrize('mode', ['cancel', 'repeated', 'timeout'])
async def test_export_git_cancel_owns_child_and_timeout(tmp_path, monkeypatch, record_property, mode):
    clean_network(monkeypatch)
    git = (await exporter(tmp_path))._transport('cancel')
    await git.initialize()
    command = await fixture_alias(tmp_path, 'cancel', """import os,sys,time
from pathlib import Path
root=Path(sys.argv[1]);(root/'active.pid').write_text(str(os.getpid()),encoding='utf-8')
time.sleep(10)
(root/'late.txt').write_text('escaped',encoding='utf-8')
""")
    deadline = asyncio.timeout(None)
    outcomes = []

    async def operation():
        try:
            async with deadline:
                return await git.command('-c', 'alias.cancel-proof=' + command, 'cancel-proof')
        except (asyncio.CancelledError, TimeoutError) as exc:
            outcomes.append(exc)
            raise

    task = asyncio.create_task(operation())
    child = None
    try:
        async with asyncio.timeout(5):
            while not await asyncio.to_thread((tmp_path / 'active.pid').exists):  # noqa: ASYNC110 - cross-process file barrier
                await asyncio.sleep(.005)
        child = psutil.Process(int(await asyncio.to_thread((tmp_path / 'active.pid').read_text, encoding='utf-8')))
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        if mode == 'timeout':
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        else:
            task.cancel()
            if mode == 'repeated':
                await asyncio.sleep(0)
                task.cancel()
        with pytest.raises(TimeoutError if mode == 'timeout' else asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)
        cause = outcomes[0].__cause__
        if mode == 'timeout':
            cause = cause.__cause__
        assert cause.lifetime.cleanup_confirmed
        assert not child.is_running() and not await asyncio.to_thread((tmp_path / 'late.txt').exists)
    finally:
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        if child is not None and child.is_running():
            child.kill()
            await asyncio.to_thread(child.wait, 5)


async def test_export_empty_configuration_has_no_ambient_git_inputs(tmp_path, monkeypatch):
    clean_network(monkeypatch)
    monkeypatch.setenv('TEMP', str(tmp_path / 'must-not-be-used'))
    owner = await exporter(tmp_path, environment={})
    git = owner._transport('empty')
    command = await fixture_alias(tmp_path, 'empty', "import os\nprint(os.environ.get('TEMP', '<unset>'))\n")
    # Supply only executable discovery required to reach the actual child on this host.
    git.environment['PATH'] = os.environ['PATH']
    for name in ('SYSTEMROOT', 'WINDIR'):
        if name in os.environ:
            git.environment[name] = os.environ[name]
    await git.initialize()
    assert (await git.command('-c', 'alias.empty-proof=' + command, 'empty-proof'))[1] == '<unset>'
