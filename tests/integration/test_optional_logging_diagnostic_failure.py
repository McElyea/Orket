"""Real isolated log writer controls for optional diagnostic append failure."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from functools import partial
from pathlib import Path

import pytest

import orket
from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.observability.log_publication import LOG_WRITER_TERMINATED_ERROR
from tests.helpers.log_process_receipts import process_readback

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
PACKAGE_ROOT = Path(orket.__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("kind", ["optional-oserror", "native-oserror", "handler-oserror", "clock-oserror", "append-valueerror"])
async def test_diagnostic_failure_retains_optional_and_required_boundaries(tmp_path, record_property, kind):
    result = await execute_owned_command(
        argv=[sys.executable, str(REPO_ROOT / "tests/helpers/optional_logging_diagnostic_probe.py"), str(tmp_path), kind],
        cwd=tmp_path, timeout_seconds=15, input_data=None, stop=asyncio.Event(), output_limit_bytes=256 * 1024,
        environment=dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONDONTWRITEBYTECODE="1",
                         PYTHONPATH=os.pathsep.join(dict.fromkeys((str(PACKAGE_ROOT), str(REPO_ROOT))))),
    )
    assert result.reason == "completed" and result.returncode == 0, result.stderr
    assert result.cleanup_confirmed and result.capture_complete
    observed = json.loads(result.stdout)
    physical = json.loads(await asyncio.to_thread((tmp_path / "probe-report.json").read_text, encoding="utf-8"))
    assert observed == physical and observed["diff_ledger"]
    assert observed["logging_origin"] == str((PACKAGE_ROOT / "orket/logging.py").resolve())
    assert observed["pending"] == [0, 0] and observed["states"] == ["closed", "closed"]
    if kind == "optional-oserror":
        assert observed["outward"] == observed["frontier"] == observed["later_frontier"] == {"result": "success"}
        assert observed["records"] == observed["delivered"] == ["diagnostic_probe", "later_optional"]
        assert observed["attempts"] == ["diagnostic_probe", "logging_subscriber_failed", "later_optional"]
        assert observed["writer_alive"] and not observed["retained_identity"] and not observed["thread_errors"]
    elif kind == "native-oserror":
        assert observed["outward"] == {"result": "failure", "type": "OSError", "identity": True}
        assert observed["frontier"] == {"result": "success"} and observed["writer_alive"]
        assert not observed["delivered"] and not observed["thread_errors"]
        assert observed["records"] == ["diagnostic_probe"]
    else:
        error = "ValueError" if kind == "append-valueerror" else "OSError"
        assert observed["frontier"] == {"result": "failure", "error": LOG_WRITER_TERMINATED_ERROR,
                                        "cause_type": error, "cause_identity": True}
        assert not observed["writer_alive"] and observed["retained_identity"]
        assert observed["thread_errors"] == [error] and not observed["delivered"]
    identities = {pid: None for pid in (result.transport_pid, result.supervisor_pid, result.command_pid) if pid}
    identities[observed["pid"]] = observed["create_time"]
    processes = await run_owned_thread(partial(process_readback, identities), label="diagnostic-process-readback")
    assert processes and all(item["status"] in {"absent", "reused"} for item in processes.values())
    record_property("diagnostic_refusal", json.dumps(dict(observation=observed, processes=processes)))
