"""Layer: integration. Retained Git objects survive canonical repository path boundaries."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import zlib
from pathlib import Path

import psutil
import pytest

from orket.adapters.vcs.gitea_export_git import GiteaExportGit
from orket.application.services.command_process_supervisor import CommandProcessSupervisor

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _fixture(root, length):
    leaf = hashlib.sha256(b'canonical retained fixture').hexdigest()
    padding = length - len(str(root)) - len(leaf) - 2
    assert 0 < padding < 200, (str(root), length, padding)
    target = root / ('p' * padding) / leaf
    payload = root / 'payload'
    payload.mkdir()
    content = b'Canonical retained Gitea payload.\n'
    (payload / 'evidence.txt').write_bytes(content)
    environment = {key: os.environ[key] for key in
        ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATH', 'PATHEXT', 'TEMP', 'TMP') if key in os.environ}
    environment.update(ORKET_DISABLE_SANDBOX='1', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never', GIT_CEILING_DIRECTORIES=str(root),
        GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
        GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
    return target, payload, content, environment


def _objects(target, commit, tree, content):
    records = {}
    for name, oid in [('commit', commit), ('tree', tree)]:
        path = target / '.git/objects' / oid[:2] / oid[2:]
        raw = path.read_bytes()
        expanded = zlib.decompress(raw)
        assert expanded.startswith(name.encode() + b' ')
        assert hashlib.sha1(expanded).hexdigest() == oid
        records[name] = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), oid=oid)
    assert (target / 'runs/boundary/evidence.txt').read_bytes() == content
    config = (target / '.git/config').read_text(encoding='utf-8')
    assert 'longpaths = true' in config
    return records


@pytest.mark.parametrize('length', [235, 247, 248, 255])
async def test_git_commit_remains_in_canonical_repository_at_path_boundary(
    tmp_path_factory, record_property, length,
):
    root = Path(await asyncio.to_thread(tmp_path_factory.mktemp, 'gc'))
    target, payload, content, environment = await asyncio.to_thread(_fixture, root, length)
    owner = CommandProcessSupervisor(target, cancellation_event='gitea_boundary_interrupted')
    observations = []

    class ObservedRunner:
        async def run(self, arguments, **options):
            assert options['cwd'] == target and options['timeout_seconds'] == 60
            assert options['output_limit_bytes'] == 262144
            result = await owner.run(arguments, **options)
            observations.append(result)
            return result

    git = GiteaExportGit(target, 'http://127.0.0.1:1/fixture.git', environment,
                        command_runner=ObservedRunner())
    record_property('gitea_repository_boundary_opening', json.dumps(dict(
        repository=str(target), length=length, payload=str(payload)), sort_keys=True))
    assert len(str(target)) == length
    await git.initialize()
    commit, tree = await git.prepare(payload, 'runs/boundary', None)
    await git.initialize()
    assert (await git.command('rev-parse', commit + ':runs/boundary'))[1] == tree
    assert (await git.command('show', commit + ':runs/boundary/evidence.txt'))[1] == content.decode().strip()
    objects = await asyncio.to_thread(_objects, target, commit, tree, content)
    assert len(observations) == 13
    assert all(row.returncode == 0 and row.reason == 'completed' and row.capture_complete
               and row.cleanup_confirmed for row in observations)
    pids = sorted({pid for row in observations for pid in
                   (row.transport_pid, row.supervisor_pid, row.command_pid) if pid is not None})
    assert pids and not any(await asyncio.gather(*(asyncio.to_thread(psutil.pid_exists, pid) for pid in pids)))
    record_property('gitea_repository_boundary_closing', json.dumps(dict(
        repository=str(target), length=length, objects=objects, commit=commit, tree=tree,
        owned_command_count=len(observations), observed_pids_absent=pids), sort_keys=True))
