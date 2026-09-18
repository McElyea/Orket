"""Factory admission and real local transport lifetime across the interface boundary."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from orket.interfaces import runtime_entrypoints

PROBE = Path(__file__).resolve().parents[1] / 'helpers/runtime_entrypoints_probe.py'


async def child(root, arguments, *, profile='developer-local'):
    import orket

    environment = dict(os.environ, PYTHONPATH=str(Path(orket.__file__).parent.parent), ORKET_DISABLE_SANDBOX='1',
                       ORKET_MODULE_PROFILE=profile, ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL='0',
                       ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL='0', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    environment.pop('ORKET_DURABLE_ROOT', None)
    process = await asyncio.create_subprocess_exec(sys.executable, *arguments, cwd=root, env=environment,
                                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    await asyncio.to_thread((root / 'stdout.log').write_bytes, stdout)
    await asyncio.to_thread((root / 'stderr.log').write_bytes, stderr)
    return process.returncode, stdout.decode(), stderr.decode()


async def probe(root, *arguments):
    code, output, error = await child(root, [str(PROBE), *arguments])
    assert code == 0, output + error
    payload = json.loads(output.strip().splitlines()[-1])
    assert payload['origin'] == runtime_entrypoints.__file__
    return payload['result']


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['api', 'cli', 'webhook'])
@pytest.mark.parametrize('profile,code', [('engine-only', 'E_CAPABILITY_DISABLED_BY_PROFILE'),
                                         ('unknown-profile', 'E_MODULE_PROFILE_UNKNOWN')])
async def test_profile_denial_precedes_transport_import_and_durable_effects(tmp_path, kind, profile, code):
    result = await probe(tmp_path, 'denied', kind, profile)
    assert result['error']['code'] == code and result['error']['ok'] is False
    assert result['before'] == result['after'] == [] and not result['durable_created']


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize('separate_stores', [False, True])
async def test_admitted_api_preserves_roots_authentication_and_real_lifespan(tmp_path, separate_stores):
    result = await probe(tmp_path, 'api-separate' if separate_stores else 'api')
    assert result['closed'] == [True, True]
    assert result['auth_statuses'] == [403, 200]
    assert result['roots'] == [str((tmp_path / name).resolve()) for name in ('one', 'two')]
    expected = ([Path(name) / 'durable/db/orket_persistence.db' for name in ('one', 'two')]
                if separate_stores else [Path('.orket/durable/db/orket_persistence.db')] * 2)
    assert list(map(Path, result['runtime_databases'])) == expected
    assert all(path in set(map(Path, result['databases'])) for path in expected)
    assert result['cross_read_statuses'] == ([404, 404] if separate_stores else [200, 200])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admitted_webhook_preserves_signature_gate_and_client_teardown(tmp_path):
    result = await probe(tmp_path, 'webhook')
    assert result['unsigned_status'] == 401 and result['signed_status'] == 200
    assert result['client_closed'] and result['handler_released'] and result['result']['status'] == 'ignored'


@pytest.mark.contract
@pytest.mark.asyncio
async def test_application_exports_keep_engine_but_retire_transport_factories(tmp_path):
    result = await probe(tmp_path, 'retired')
    assert all(names == [] for names in result['remaining'].values())
    assert result['engine_export_retained'] and result['config_export_retained']


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize('profile,expected', [('developer-local', 0), ('api-runtime', 1)])
async def test_public_cli_entrypoint_preserves_module_admission_status(tmp_path, profile, expected):
    code, output, error = await child(tmp_path, ['-m', 'orket.cli', 'runtime', '--help'], profile=profile)
    assert code == expected, output + error
    if expected == 0:
        assert 'usage: orket runtime' in output
    else:
        assert '[CRITICAL ERROR]' in output and 'E_CAPABILITY_DISABLED_BY_PROFILE' in output and 'cli.runtime' in output
        assert (tmp_path / 'workspace/default/orket_crash.log').is_file()
