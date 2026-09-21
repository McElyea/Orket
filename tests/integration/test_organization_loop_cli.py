"""Native loop dispatch checked against retained SQLite and closed runtime owners."""
import asyncio
import json
import os
import sys
from pathlib import Path

import aiosqlite
import pytest

import orket
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from tests.integration.test_organization_loop_ownership import seed_organization

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]


@pytest.mark.parametrize('case', ['accepted', 'unfinished'])
async def test_native_organization_loop_preserves_truth_and_cleanup(test_root, case):
    await asyncio.to_thread(seed_organization, test_root)
    harness = (await asyncio.to_thread(Path(__file__).resolve)).parents[2]
    environment = dict(os.environ, PYTHONPATH=str(harness), ORKET_DISABLE_SANDBOX='1',
                       ORKET_DURABLE_ROOT=str(test_root / '.orket/durable'), ORKET_RUN_LEDGER_MODE='sqlite')
    environment.pop('PYTEST_CURRENT_TEST', None)
    outcome = await CommandProcessSupervisor(test_root, cancellation_event='verification_process_cancelled').run(
        [sys.executable, '-m', 'tests.helpers.organization_loop_cli_worker', str(test_root), case],
        cwd=test_root, environment=environment, timeout_seconds=30,
    )
    await asyncio.to_thread((test_root / 'cli-stdout.log').write_bytes, outcome.stdout)
    await asyncio.to_thread((test_root / 'cli-stderr.log').write_bytes, outcome.stderr)
    assert outcome.cleanup_confirmed and outcome.capture_complete
    assert outcome.returncode == (0 if case == 'accepted' else 1), (outcome.stdout, outcome.stderr)
    observed = json.loads(await asyncio.to_thread((test_root / 'cli-observation.json').read_text, encoding='utf-8'))
    assert await asyncio.to_thread(Path(observed['runtime_origin']).resolve) == await asyncio.to_thread(Path(orket.__file__).resolve)
    assert observed['engine_closed'] == observed['pipeline_closed'] == observed['loops_stopped'] == [True]
    result, = observed['results']
    assert result['succeeded'] is (case == 'accepted')
    database = Path(observed['databases'][0])
    assert database.is_relative_to(test_root)
    async with aiosqlite.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
        ledger, = await (await connection.execute('SELECT status FROM run_ledger')).fetchall()
        assert (ledger[0] == 'done') is (case == 'accepted')
        exists = await (await connection.execute("SELECT name FROM sqlite_master WHERE name='success_ledger'")).fetchone()
        count = (await (await connection.execute('SELECT COUNT(*) FROM success_ledger')).fetchone())[0] if exists else 0
        assert count == int(case == 'accepted')
