"""Layer: integration. Actual Git, payload files and native export ownership."""
import asyncio
import hashlib
import json
import os
import shlex
import shutil
import sys
import threading
from pathlib import Path

import psutil
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.gitea_artifact_exporter_factory import create_gitea_artifact_exporter
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_short_http_ownership import clean_network

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def exporter(root, *, environment=None, url='http://127.0.0.1:1'):
    selected = dict(os.environ if environment is None else environment)
    selected.update(ORKET_GITEA_ARTIFACT_EXPORT='1', GITEA_URL=url,
        GITEA_ADMIN_USER='fixture', GITEA_ADMIN_PASSWORD='public-password',
        ORKET_GITEA_ARTIFACT_OWNER='fixture', ORKET_GITEA_ARTIFACT_REPO='fixture',
        ORKET_GITEA_ARTIFACT_CACHE_ROOT=str(root / 'cache'))
    return await run_owned_thread(lambda: create_gitea_artifact_exporter(
        root / 'workspace', environment=selected, invocation_root=root), label='export-fixture-construction')


def run_values(summary):
    return dict(run_id='owned-payload', run_type='epic', run_name='fixture', build_id='fixture',
                session_status='done', summary=summary, export_day='2026-09-22',
                export_time='2026-09-22T12:00:00+00:00')


def held_payload(monkeypatch, owner):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = owner._build_payload

    def held(*args, **options):
        entered.set()
        try:
            assert release.wait(5), 'Payload fixture did not release'
            return original(*args, **options)
        finally:
            finished.set()

    monkeypatch.setattr(owner, '_build_payload', held)
    return entered, release, finished


async def fixture_alias(root, name, content):
    path = root / (name + '.py')
    await asyncio.to_thread(path.write_text, content, encoding='utf-8', newline='\n')
    return '!' + ' '.join(shlex.quote(value) for value in (Path(sys.executable).as_posix(), path.as_posix(), root.as_posix()))


def physical_sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git_repository_state(git):
    directory = git.repo_dir / '.git'
    config = (directory / 'config').read_text(encoding='utf-8')
    head = (directory / 'HEAD').read_text(encoding='utf-8').strip()
    durable = any(line.strip().lower() == 'longpaths = true' for line in config.splitlines())
    return dict(objects=(directory / 'objects').is_dir(), head=head, durable_longpaths=durable)


# Layer: integration. Real Git process and physical short/long repository state.
async def test_export_git_initializes_at_long_path_boundary(tmp_path_factory, monkeypatch, record_property):
    clean_network(monkeypatch)
    short_root = await asyncio.to_thread(tmp_path_factory.mktemp, 'gs')
    long_base = await asyncio.to_thread(tmp_path_factory.mktemp, 'gl')
    repo_suffix = Path('cache/repo_cache') / ('0' * 64)
    padding = 236 - len(str(long_base / repo_suffix)) - 1
    if not 0 < padding <= 200:
        raise AssertionError(dict(reason='fixture cannot reach exact boundary', base=str(long_base), padding=padding))
    long_root = long_base / ('p' * padding)
    await asyncio.to_thread(long_root.mkdir)

    short_owner = await exporter(short_root)
    long_owner = await exporter(long_root)
    short_git = short_owner._transport('short-boundary')
    long_git = long_owner._transport('long-boundary')
    repo_lengths = [len(str(git.repo_dir)) for git in (short_git, long_git)]
    object_length = len(str(long_git.repo_dir / '.git/objects'))

    executables = []
    for git in (short_git, long_git):
        selected = await asyncio.to_thread(shutil.which, 'git', path=git.environment['PATH'])
        if selected is None:
            raise AssertionError('captured PATH does not resolve Git')
        executables.append(await asyncio.to_thread(Path(selected).resolve))
    executable_sha256 = await asyncio.to_thread(physical_sha256, executables[0])

    await asyncio.wait_for(short_git.initialize(), 10)
    code, short_version = await asyncio.wait_for(short_git.command('--version'), 10)
    short_state = await asyncio.to_thread(git_repository_state, short_git)
    opening = dict(executable=str(executables[0]), executable_sha256=executable_sha256,
        version=short_version, short_repo_length=repo_lengths[0], long_repo_length=repo_lengths[1],
        objects_length=object_length, short_state=short_state)
    record_property('gitea_long_path_opening', json.dumps(opening, sort_keys=True))

    assert all(git.environment['GIT_CONFIG_NOSYSTEM'] == '1' for git in (short_git, long_git))
    assert all(git.environment['GIT_CONFIG_GLOBAL'] == os.devnull for git in (short_git, long_git))
    assert executables[0] == executables[1] and await asyncio.to_thread(executables[0].is_file)
    assert repo_lengths[0] < 236 and repo_lengths[1] == 236 and object_length == 249
    assert code == 0 and short_version.startswith('git version ')
    assert short_state['objects'] and short_state['head'].startswith('ref: refs/heads/')
    assert short_state['durable_longpaths']

    await asyncio.wait_for(long_git.initialize(), 10)
    code, long_version = await asyncio.wait_for(long_git.command('--version'), 10)
    long_state = await asyncio.to_thread(git_repository_state, long_git)
    closing_sha256 = await asyncio.to_thread(physical_sha256, executables[1])
    closing = dict(version=long_version, executable_sha256=closing_sha256, long_state=long_state)
    record_property('gitea_long_path_closing', json.dumps(closing, sort_keys=True))
    assert code == 0 and long_version == short_version and closing_sha256 == executable_sha256
    assert long_state['objects'] and long_state['head'].startswith('ref: refs/heads/')
    assert long_state['durable_longpaths']


@pytest.mark.parametrize('mode', ['supplied', 'ambient', 'unchanged'])
async def test_export_git_uses_construction_environment(tmp_path, monkeypatch, mode):
    clean_network(monkeypatch)
    captured, changed = str(tmp_path / 'captured-temp'), str(tmp_path / 'changed-temp')
    monkeypatch.setenv('TEMP', captured)
    environment = dict(os.environ, TEMP=captured) if mode != 'ambient' else None
    owner = await exporter(tmp_path, environment=environment)
    if mode != 'unchanged':
        monkeypatch.setenv('TEMP', changed)
    git = owner._transport('environment')
    await git.initialize()
    command = await fixture_alias(tmp_path, 'environment', "import os\nprint(os.environ.get('TEMP', '<unset>'))\n")
    code, observed = await asyncio.wait_for(git.command('-c', 'alias.capture-input=' + command, 'capture-input'), 10)
    assert code == 0 and observed == captured


@pytest.mark.parametrize('mutate', [False, True], ids=['unchanged', 'mutated'])
@pytest.mark.parametrize('mode', ['cancel', 'repeated', 'timeout'])
async def test_export_preparation_retains_native_payload(tmp_path, monkeypatch, mutate, mode):
    clean_network(monkeypatch)
    owner = await exporter(tmp_path)
    entered, release, finished = held_payload(monkeypatch, owner)
    summary = {'nested': ['captured']}
    deadline = asyncio.timeout(None)

    async def prepare():
        async with deadline:
            return await owner.prepare_export(**run_values(summary))

    task = asyncio.create_task(prepare())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if mutate:
            summary['nested'].append('changed')
        if mode == 'timeout':
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        else:
            task.cancel()
        await asyncio.sleep(.03)
        if mode == 'repeated':
            task.cancel()
            await asyncio.sleep(.01)
        assert not task.done() and not finished.is_set()
        release.set()
        with pytest.raises(TimeoutError if mode == 'timeout' else asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)
        manifests = await asyncio.to_thread(lambda: list((tmp_path / 'cache/payload').glob('*/manifest.json')))
        assert len(manifests) == 1
        manifest = json.loads(await asyncio.to_thread(manifests[0].read_text, encoding='utf-8'))
        assert manifest['summary'] == {'nested': ['captured']} and finished.is_set()
        assert not await asyncio.to_thread((tmp_path / 'cache/repo_cache').exists)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert await asyncio.to_thread(finished.wait, 5)


@pytest.mark.parametrize('mutate', [False, True], ids=['unchanged', 'mutated'])
async def test_export_commit_keeps_admitted_summary(tmp_path, monkeypatch, mutate):
    clean_network(monkeypatch)

    async def absent(_request):
        return 404, {'message': 'controlled absent repository'}

    async with observed_http_server(absent) as server:
        owner = await exporter(tmp_path, url=server[0])
        entered, release, finished = held_payload(monkeypatch, owner)
        summary = {'nested': ['captured']}
        task = asyncio.create_task(owner.prepare_export(**run_values(summary)))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            if mutate:
                summary['nested'].append('changed')
            release.set()
            intent = await asyncio.wait_for(asyncio.shield(task), 10)
            git = owner._transport(intent.run_id)
            code, raw = await git.command('show', intent.commit + ':' + intent.run_path + '/manifest.json')
            assert code == 0 and json.loads(raw)['summary'] == {'nested': ['captured']}
            assert len(server[1]) == 1 and server[1][0][0].startswith('GET ') and finished.is_set()
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert await asyncio.to_thread(finished.wait, 5)


async def descendant_fixture(root, detached):
    child = """import os,sys,time
from pathlib import Path
root=Path(sys.argv[1]);(root/'child.pid').write_text(str(os.getpid()),encoding='utf-8')
if sys.argv[2]=='detached':
 stop=time.monotonic()+10
 while not (root/'release.txt').exists():
  if time.monotonic()>stop:raise TimeoutError('Fixture release missed')
  time.sleep(.005)
(root/'effect.txt').write_text('observed',encoding='utf-8')
"""
    await asyncio.to_thread((root / 'child.py').write_text, child, encoding='utf-8', newline='\n')
    mode = 'detached' if detached else 'joined'
    parent = f"""import subprocess,sys,time
from pathlib import Path
root=Path(sys.argv[1])
child=subprocess.Popen([sys.executable,str(root/'child.py'),str(root),'{mode}'],
 stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)
stop=time.monotonic()+5
while not (root/'child.pid').exists():
 if time.monotonic()>stop:raise TimeoutError('Fixture child did not start')
 time.sleep(.005)
if '{mode}'=='joined':assert child.wait(5)==0
"""
    return await fixture_alias(root, 'parent', parent)


@pytest.mark.parametrize('detached', [False, True], ids=['joined-control', 'orphan'])
async def test_export_git_confirms_descendant_teardown_before_success(tmp_path, monkeypatch, detached):
    clean_network(monkeypatch)
    owner = await exporter(tmp_path)
    git = owner._transport('descendant')
    await git.initialize()
    command = await descendant_fixture(tmp_path, detached)
    child = None
    try:
        code, observed = await asyncio.wait_for(git.command('-c', 'alias.descendant-proof=' + command, 'descendant-proof'), 10)
        pid = int(await asyncio.to_thread((tmp_path / 'child.pid').read_text, encoding='utf-8'))
        try:
            child = psutil.Process(pid)
            alive = child.is_running()
        except psutil.NoSuchProcess:
            alive = False
        assert code == 0 and observed == '' and not alive
        assert await asyncio.to_thread((tmp_path / 'effect.txt').exists) is not detached
    finally:
        await asyncio.to_thread((tmp_path / 'release.txt').touch)
        if child is not None:
            try:
                if child.is_running():
                    child.kill()
                await asyncio.to_thread(child.wait, 5)
            except psutil.NoSuchProcess:
                pass
