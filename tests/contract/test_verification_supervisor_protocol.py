"""Contract negatives using a substitute supervisor; not live OS-ownership proof."""
from __future__ import annotations

import asyncio
import sys

import pytest

from orket.adapters.execution import owned_command_process
from orket.application.services.runtime_verifier import RuntimeVerifier

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("mutation", [
    "record['request_id'] = 'foreign-request'",
    "record['supervisor_pid'] = 0",
    "record['cleanup_confirmed'] = False",
    "record['capture_complete'] = False",
    "record['diagnostics'] = 'not-a-list'",
    "record['command_pid'] = 'not-a-pid'",
    "record['command_pid'] = None",
    "record['backend'] = 'unavailable'",
    "record['worker_exit'] = 1",
    "record = {}",
])
# Layer: contract
async def test_invalid_lifetime_cannot_become_success(tmp_path, monkeypatch, mutation):
    worker = tmp_path / "protocol_fixture.py"
    source = (
        "import json, os, sys\nrequest=json.loads(sys.stdin.buffer.readline())\n"
        "record = dict(schema_version='owned_command.v1', request_id=request['request_id'], supervisor_pid=os.getpid(), "
        "command_pid=123, reason='completed', cleanup_confirmed=True, capture_complete=True, "
        "backend='windows_job' if os.name == 'nt' else 'linux_subreaper', returncode=0, stdout='', stderr='', diagnostics=[])\n"
        f"{mutation}\nprint(json.dumps(record), flush=True)\nsys.exit(record.get('worker_exit', 0))\n"
    )
    await asyncio.to_thread(worker.write_text, source, encoding="utf-8")
    monkeypatch.setattr(owned_command_process, "WORKER", worker)
    result = await RuntimeVerifier(tmp_path, issue_params={"runtime_verifier": {
        "commands": [[sys.executable, "-c", "raise SystemExit(0)"]],
    }}).verify()
    assert not result.ok and result.failure_breakdown == {"cleanup_unconfirmed": 1}
    receipt = result.command_results[0]
    assert receipt["returncode"] == 125
    assert receipt["process_lifetime"]["cleanup_confirmed"] is False
    assert receipt["process_lifetime"]["diagnostics"][0].startswith("supervisor_protocol_invalid:")
