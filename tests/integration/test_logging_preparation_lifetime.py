"""Integration: real writer start, interruption and process-owned daemon teardown."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.adapters.observability import log_publication
from tests.helpers.log_process_receipts import process_readback
from tests.integration.test_failure_diagnostic_refusals import _assert_child_origins, _selected_pythonpath

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / "helpers/logging_preparation_worker.py"
FAULT_CASES = [(phase, kind) for phase in ("before", "after")
               for kind in ("RuntimeError", "OSError", "SystemExit", "KeyboardInterrupt", "CancelledError")]


async def run_worker(tmp_path, worker, arguments, record_property):
    temporary = tmp_path / "temp"
    await asyncio.to_thread(temporary.mkdir)
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONDONTWRITEBYTECODE="1",
        TMP=str(temporary), TEMP=str(temporary), PYTHONPATH=await asyncio.to_thread(_selected_pythonpath))
    result = await execute_owned_command(
        argv=[sys.executable, str(worker), str(tmp_path), *arguments], cwd=tmp_path,
        environment=environment, timeout_seconds=25, input_data=None, stop=asyncio.Event(),
        output_limit_bytes=256 * 1024)
    record_property("child_lifetime", json.dumps(result.lifetime()))
    assert result.reason == "completed" and result.returncode == 0, (result.lifetime(), result.stdout, result.stderr)
    assert result.cleanup_confirmed and result.capture_complete
    data = json.loads(await asyncio.to_thread((tmp_path / "result.json").read_text, encoding="utf-8"))
    await asyncio.to_thread(_assert_child_origins, data)
    identity = data["process_identity"]
    identities = {pid: None for pid in (result.transport_pid, result.supervisor_pid, result.command_pid) if pid is not None}
    identities[identity["pid"]] = identity["create_time"]
    observed = await asyncio.to_thread(process_readback, identities)
    record_property("logging_preparation", json.dumps({"child": data, "processes": observed}))
    assert observed and all(row["status"] in {"absent", "reused"} for row in observed.values())
    return data


@pytest.mark.parametrize("phase,kind", [*FAULT_CASES, ("before", "success")])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
async def test_preparation_retains_start_attempt_and_process_writer(tmp_path, phase, kind, stop, record_property):
    data = await run_worker(tmp_path, WORKER, [phase, kind, stop], record_property)
    assert data["publication_origin"] == await asyncio.to_thread(lambda: str(Path(log_publication.__file__).resolve()))
    actual_hash = await asyncio.to_thread(lambda: hashlib.sha256(Path(log_publication.__file__).read_bytes()).hexdigest())
    assert data["publication_sha256"] == actual_hash
    assert (data["phase"], data["kind"], data["stop"]) == (phase, kind, stop)
    assert data["native_start_settled"] and data["original_graph_preserved"] and not data["watchdog_expired"]
    assert data["start_calls"] == 1 and data["caller_cancel_requests"] == {"none": 0, "cancel": 2, "timeout": 1}[stop]
    assert data["prepared"] == (kind == "success")
    assert data["writer_alive_at_return"] == (phase == "after" or kind == "success")


async def test_concurrent_applications_borrow_one_writer_with_captured_values(tmp_path, record_property):
    worker = WORKER.with_name("logging_preparation_context_worker.py")
    data = await run_worker(tmp_path, worker, [], record_property)
    assert all(data[key] for key in ("one_writer", "configuration_refused", "zero_effect_initial_refusals",
        "loop_native_hooks_absent", "context_restored", "exact_physical_records", "writer_alive_at_return"))
