"""Layer: integration. Audit settlement preserves its invocation's actual primary failure."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from functools import partial
from pathlib import Path
from typing import Any

import pytest

import orket
from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.adapters.execution.owned_io import run_owned_thread
from tests.helpers.log_process_receipts import process_readback

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).resolve().parents[1] / "helpers" / "audit_double_failure_probe.py"
PACKAGE_ROOT = Path(orket.__file__).resolve().parent.parent
CHILD_PYTHONPATH = os.pathsep.join(dict.fromkeys((str(PACKAGE_ROOT), str(REPO_ROOT))))
EXPECTED_ORIGINS = {
    "logging": str((PACKAGE_ROOT / "orket" / "logging.py").resolve()),
    "runtime_event": str((PACKAGE_ROOT / "orket" / "core" / "runtime_event.py").resolve()),
    "extension_runtime": str((PACKAGE_ROOT / "orket" / "extensions" / "runtime.py").resolve()),
    "audit": str((REPO_ROOT / "scripts" / "security" / "build_tool_gate_audit.py").resolve()),
    "helper": str(PROBE.resolve()),
}
WRITER_ERROR = "E_LOG_WRITER_TERMINATED: log writer stopped before the requested frontier"
SETTLEMENT_NOTE = (
    "Audit log settlement failed: code=E_LOG_WRITER_TERMINATED; "
    "secondary_type=RuntimeError; daemon_cause_type=ValueError"
)
CLOSE_MESSAGE = "controlled audit engine close failure"
FATAL_MESSAGE = "controlled fatal log writer failure"
AMBIENT_MESSAGE = "controlled ambient caller error"
PRIOR_CAUSE_MESSAGE = "controlled prior close cause"
PRIOR_CONTEXT_MESSAGE = "controlled prior close context"
PRIOR_NOTE_MESSAGE = "controlled pre-existing close note"


def _read_report(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


async def _run_probe(tmp_path: Path, scenario: str, record_property) -> dict[str, Any]:
    scenario_root = await run_owned_thread(
        lambda: (tmp_path / scenario).resolve(),
        label="audit-double-failure-root",
    )
    environment = dict(
        os.environ,
        ORKET_DISABLE_SANDBOX="1",
        ORKET_LOG_QUEUE_MAX="1000",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=CHILD_PYTHONPATH,
    )
    result = await execute_owned_command(
        argv=[sys.executable, str(PROBE), scenario, str(scenario_root)],
        cwd=tmp_path,
        environment=environment,
        timeout_seconds=12,
        input_data=None,
        stop=asyncio.Event(),
        output_limit_bytes=256 * 1024,
    )
    assert result.reason == "completed", (result.lifetime(), result.stderr)
    assert result.returncode == 0 and result.cleanup_confirmed and result.capture_complete, result.lifetime()
    observation = json.loads(result.stdout)
    report_path = scenario_root / "probe-report.json"
    physical, report_sha256 = await run_owned_thread(
        partial(_read_report, report_path),
        label="audit-double-failure-report-readback",
    )
    assert observation == physical
    assert observation["schema_version"] == "audit_double_failure_probe.v1"
    assert observation["scenario"] == scenario
    assert observation["report_path"] == str(report_path)
    assert observation["output_path"] == str(scenario_root / "audit-output.json")
    assert observation["origins"] == EXPECTED_ORIGINS
    assert isinstance(observation.get("diff_ledger"), list) and observation["diff_ledger"]
    identity = observation["process_identity"]
    assert type(identity["pid"]) is int and identity["pid"] > 0
    assert type(identity["create_time"]) in {int, float} and identity["create_time"] > 0
    identities = {
        pid: None for pid in (result.transport_pid, result.supervisor_pid, result.command_pid) if pid is not None
    }
    identities[identity["pid"]] = identity["create_time"]
    process_observation = await run_owned_thread(
        partial(process_readback, identities),
        label="audit-double-failure-process-readback",
    )
    receipt = {
        "scenario": scenario,
        "observation": observation,
        "canonical_report_sha256": report_sha256,
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stdout_matches_canonical_payload": observation == physical,
        "process_lifetime": {**result.lifetime(), "returncode": result.returncode},
        "process_readback": process_observation,
    }
    record_property("audit_double_failure_receipt", json.dumps(receipt, sort_keys=True))
    assert process_observation
    assert all(row["status"] in {"absent", "reused"} for row in process_observation.values()), process_observation
    return observation


def _basic(error_type: str, message: str) -> dict[str, Any]:
    code = message.partition(":")[0] if message.startswith("E_") and ":" in message else None
    return {"type": error_type, "message": message, "code": code}


def _assert_settlement(error: dict[str, Any], fatal: dict[str, Any]) -> None:
    assert {key: error[key] for key in ("type", "message", "code")} == _basic("RuntimeError", WRITER_ERROR)
    assert error["notes"] == []
    assert error["suppress_context"] is True
    assert error["cause"] == fatal


def _assert_common(observed: dict[str, Any], fatal: dict[str, Any]) -> None:
    assert observed["settlement"]["calls"] == 1
    assert observed["settlement"]["inside_temp_owner"] is True
    _assert_settlement(observed["settlement"]["error"], fatal)
    assert observed["settlement"]["cause_is_writer_failure"] is True
    assert observed["fatal_append"]["calls"] == 3 and observed["fatal_append"]["reached"] is True
    assert observed["fatal_append"]["thread_error"] == fatal
    assert observed["writer_failure"] == fatal and observed["writer_failure_is_fatal"] is True
    assert observed["fatal_append"]["thread"]["name"] == "orket-log-writer"
    assert observed["fatal_append"]["thread"]["daemon"] is True
    assert observed["same_writer_after_audit"] is True
    assert observed["writer_after_audit"]["alive"] is False
    assert observed["second_settlement"]["status"] == "error"
    _assert_settlement(observed["second_settlement"]["error"], fatal)
    assert observed["same_writer_after_second"] is True
    assert observed["temp_owner"]["exit_entered"] is True
    assert observed["temp_owner"]["cleanup_finished"] is True
    assert observed["temp_owner"]["temp_absent"] is True
    assert observed["output_present"] is False and observed["audit_stdout"] == ""
    sequence = observed["sequence"]
    assert sequence.index("settlement-enter") < sequence.index("settlement-error")
    assert sequence.index("settlement-error") < sequence.index("settlement-exit")
    assert sequence.index("settlement-exit") < sequence.index("owner-exit")


def _close_detail(*, notes: list[str]) -> dict[str, Any]:
    return {
        **_basic("OSError", CLOSE_MESSAGE),
        "notes": notes,
        "suppress_context": True,
        "cause": _basic("EOFError", PRIOR_CAUSE_MESSAGE),
        "context": _basic("LookupError", PRIOR_CONTEXT_MESSAGE),
    }


# Layer: integration
async def test_audit_preserves_required_close_error_when_log_settlement_also_fails(
    tmp_path: Path, record_property,
) -> None:
    observed = await _run_probe(tmp_path, "combined-close", record_property)
    fatal = _basic("ValueError", FATAL_MESSAGE)
    close_before = _close_detail(notes=[PRIOR_NOTE_MESSAGE])
    # The real collector's unwind supplies its gate error before audit settlement begins.
    close_entry = {**close_before, "context": _basic("RuntimeOutcomeError", "audit gate denied")}
    close_outward = {**close_entry, "notes": [PRIOR_NOTE_MESSAGE, SETTLEMENT_NOTE]}

    _assert_common(observed, fatal)
    assert observed["ambient_error"] is None
    assert observed["close"] == {
        "delegated": True,
        "failure_raised": True,
        "graph_before": close_before,
    }
    assert observed["settlement"]["entry_exception"] == close_entry
    sequence = observed["sequence"]
    assert sequence.index("fatal-append") < sequence.index("close-failure")
    assert sequence.index("close-failure") < sequence.index("settlement-enter")

    # These final assertions are the intended opening failure on the old finally-masking behavior.
    assert observed["audit_exit_code"] is None
    assert observed["outward_is_close_exception"] is True
    assert observed["outward_contains_close_traceback"] is True
    assert observed["outward"] == close_outward
    assert observed["temp_owner"]["exit_exception"] == close_outward
    assert observed["exported_writer_error"] == WRITER_ERROR


# Layer: integration
async def test_audit_fatal_settlement_ignores_unrelated_handled_caller_exception(
    tmp_path: Path, record_property,
) -> None:
    observed = await _run_probe(tmp_path, "ambient-healthy", record_property)
    fatal = _basic("ValueError", FATAL_MESSAGE)
    ambient = _basic("LookupError", AMBIENT_MESSAGE)

    _assert_common(observed, fatal)
    assert observed["ambient_error"]["type"] == ambient["type"]
    assert observed["ambient_error"]["message"] == ambient["message"]
    assert observed["close"] == {"delegated": True, "failure_raised": False, "graph_before": None}
    assert observed["settlement"]["entry_exception"]["type"] == ambient["type"]
    assert observed["settlement"]["entry_exception"]["message"] == ambient["message"]
    assert observed["audit_exit_code"] is None
    _assert_settlement(observed["outward"], fatal)
    assert observed["temp_owner"]["exit_exception"] == observed["outward"]
