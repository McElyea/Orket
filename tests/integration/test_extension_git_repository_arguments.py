"""Layer: integration. Native installation keeps one checkout at long Git-directory boundaries."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

import psutil
import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.application.services.extension_catalog_commands import list_installed_extensions, prepare_extension_manager
from tests.integration.test_extension_git_longpath_installation import _git
from tests.runtime.test_extension_capability_authorization import MEMORY_QUERY_SOURCE, _init_sdk_repo

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _prepare(root: Path, checkout_length: int):
    source = root / 'source'
    source.mkdir()
    (source / '.gitattributes').write_text('* -text\n', encoding='utf-8')
    _init_sdk_repo(source, module_source=MEMORY_QUERY_SOURCE, required_capabilities=['memory.query'])
    commit = _git(source, 'rev-parse', '--verify', '--end-of-options', 'HEAD^{commit}')
    base = root / 'durable'
    suffix = len(str(Path('extensions') / 'checkout-xxxxxxxx')) + 1
    padding = checkout_length - suffix - len(str(base)) - 1
    assert 0 < padding < 200, (str(root), checkout_length, padding)
    durable = base / ('p' * padding)
    expected = {name: (source / name).read_bytes() for name in
                ('.gitattributes', 'extension.yaml', 'sdk_auth_extension.py')}
    return source, durable, commit, expected


@pytest.mark.parametrize('checkout_length', [200, 217])
async def test_install_resolves_and_checks_out_commit_at_git_directory_boundary(
    tmp_path_factory, monkeypatch, record_property, checkout_length,
):
    root = Path(await asyncio.to_thread(tmp_path_factory.mktemp, 'gitdir'))
    source, durable, commit, expected = await asyncio.to_thread(_prepare, root, checkout_length)
    original, observations = CommandProcessSupervisor.run, []

    async def observed(owner, *args, **kwargs):
        result = await original(owner, *args, **kwargs)
        observations.append(result)
        return result

    monkeypatch.setattr(CommandProcessSupervisor, 'run', observed)
    environment = dict(os.environ, ORKET_DURABLE_ROOT=str(durable))
    manager = await prepare_extension_manager(catalog_path=root / 'catalog.json', project_root=root,
        invocation_root=root, environment=environment)
    record = await manager.install_from_repo(str(source))
    checkout = Path(record.path)
    assert len(str(checkout)) == checkout_length and checkout.parent == durable / 'extensions'
    assert len(str(checkout / '.git')) == checkout_length + 5
    assert record.resolved_commit_sha == commit
    for name, content in expected.items():
        assert await asyncio.to_thread((checkout / name).read_bytes) == content
    head = await asyncio.to_thread((checkout / '.git/HEAD').read_text, encoding='utf-8')
    assert head.strip() == commit
    catalog = json.loads(await asyncio.to_thread(manager.catalog_path.read_text, encoding='utf-8'))
    assert catalog == {'extensions': [manager.catalog.row_from_record(record)]}
    restarted = await prepare_extension_manager(catalog_path=manager.catalog_path, project_root=root,
        invocation_root=root, environment=environment)
    assert await list_installed_extensions(restarted) == [record]
    assert len(observations) == 3
    assert all(row.returncode == 0 and row.reason == 'completed' and row.cleanup_confirmed
               and row.capture_complete for row in observations)
    pids = sorted({pid for row in observations for pid in
                   (row.transport_pid, row.supervisor_pid, row.command_pid) if pid is not None})
    assert pids and not any(await asyncio.gather(*(asyncio.to_thread(psutil.pid_exists, pid) for pid in pids)))
    record_property('extension_git_directory_boundary', json.dumps(dict(
        checkout=str(checkout), checkout_length=checkout_length, git_directory_length=checkout_length + 5,
        commit=commit, head=head.strip(), catalog_sha256=hashlib.sha256(
            await asyncio.to_thread(manager.catalog_path.read_bytes)).hexdigest(),
        owned_command_count=len(observations), observed_pids_absent=pids), sort_keys=True))
