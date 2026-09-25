"""Layer: integration. Real daemon lifetime and native frontier controls."""
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
from tests.helpers.log_process_receipts import process_readback

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).resolve().parents[1] / "helpers" / "log_frontier_probe.py"
PACKAGE_ROOT = Path(orket.__file__).resolve().parent.parent
EXPECTED_LOGGING_ORIGIN = str((PACKAGE_ROOT / "orket" / "logging.py").resolve())
CHILD_PYTHONPATH = os.pathsep.join(dict.fromkeys((str(PACKAGE_ROOT), str(REPO_ROOT))))
WRITER_ERROR = "E_LOG_WRITER_TERMINATED: log writer stopped before the requested frontier"
LOOP_ERROR = "E_LOG_WRITE_FRONTIER_REQUIRES_NATIVE_CONTEXT: settlement blocks the calling thread"


def _read_events(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [json.loads(line)["event"] for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


async def _run_probe(tmp_path: Path, scenario: str, record_property) -> dict:
    scenario_root = await run_owned_thread(
        lambda: (tmp_path / scenario).resolve(),
        label="log-frontier-scenario-root",
    )
    environment = dict(
        os.environ,
        ORKET_DISABLE_SANDBOX="1",
        ORKET_LOG_QUEUE_MAX="2",
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
    physical_report = await run_owned_thread(
        partial(_read_json, report_path),
        label="log-frontier-report-readback",
    )
    assert observation == physical_report
    assert isinstance(observation.get("diff_ledger"), list) and observation["diff_ledger"]
    assert observation["schema_version"] == "log_frontier_probe.v1"
    assert observation["scenario"] == scenario
    assert observation["report_path"] == str(report_path)
    assert observation["path"] == str(scenario_root / "events.jsonl")
    assert observation["logging_origin"] == EXPECTED_LOGGING_ORIGIN
    identity = observation["process_identity"]
    assert type(identity["pid"]) is int and identity["pid"] > 0
    assert type(identity["create_time"]) in {int, float} and identity["create_time"] > 0
    identities = {
        pid: None for pid in (result.transport_pid, result.supervisor_pid, result.command_pid) if pid is not None
    }
    identities[identity["pid"]] = identity["create_time"]
    process_observation = await run_owned_thread(
        partial(process_readback, identities),
        label="log-frontier-probe-process-readback",
    )
    receipt = {
        "scenario": scenario,
        "observation": observation,
        "process_lifetime": {**result.lifetime(), "returncode": result.returncode},
        "process_readback": process_observation,
    }
    record_property("log_write_frontier_lifetime_receipt", json.dumps(receipt, sort_keys=True))
    assert process_observation
    assert all(row["status"] in {"absent", "reused"} for row in process_observation.values()), process_observation
    return observation


async def _physical_events(observation: dict) -> list[str]:
    return await run_owned_thread(
        partial(_read_events, Path(observation["path"])),
        label="log-frontier-physical-readback",
    )


# Layer: integration
async def test_native_frontier_starts_one_unprepared_daemon_and_reuses_it(tmp_path: Path, record_property) -> None:
    observed = await _run_probe(tmp_path, "unprepared-reuse", record_property)
    assert observed["before"] is None
    assert observed["first_settlement"] == {"status": "settled"}
    assert observed["second_settlement"] == {"status": "settled"}
    assert observed["same_writer"] is True and observed["writer_name_count"] == 1
    assert observed["writer"]["name"] == "orket-log-writer"
    assert observed["writer"]["daemon"] is True and observed["writer"]["alive"] is True
    assert observed["writer"]["ident"] and observed["writer"]["native_id"]
    assert observed["marker"] == {"attempts": 2, "admissions": 2}
    assert observed["append_events"] == ["queued-after-first-settlement"]
    assert observed["drops_before"] == observed["drops_after"] == 0
    assert await _physical_events(observed) == ["queued-after-first-settlement"]


# Layer: integration
async def test_frontier_refuses_running_loop_before_queue_or_thread_effects(tmp_path: Path, record_property) -> None:
    observed = await _run_probe(tmp_path, "loop-refusal", record_property)
    assert observed["refusal"] == {
        "status": "error",
        "error": {"type": "RuntimeError", "message": LOOP_ERROR, "cause_type": None, "cause_message": None},
    }
    assert observed["before"] == observed["after"] == {"writer": None, "queue_size": 0, "drops": 0}
    assert observed["marker"] == {"attempts": 0, "admissions": 0}
    assert await _physical_events(observed) == []


# Layer: integration
async def test_optional_oserror_settles_without_delivery_drop_or_marker_append(
    tmp_path: Path, record_property,
) -> None:
    observed = await _run_probe(tmp_path, "optional-oserror", record_property)
    assert observed["settlement"] == {"status": "settled"}
    assert observed["calls"] == ["optional-oserror"]
    assert observed["physical_events"] == [] and await _physical_events(observed) == []
    assert observed["marker"] == {"attempts": 1, "admissions": 1}
    assert observed["drops_before"] == observed["drops_after"] == 0
    assert observed["writer"]["alive"] is True


# Layer: integration
async def test_full_queue_frontier_waits_then_excludes_later_accepted_append(
    tmp_path: Path, record_property,
) -> None:
    observed = await _run_probe(tmp_path, "full-queue-cutoff", record_property)
    expected = ["held-first", "prior-one", "prior-two", "later"]
    assert observed["queue_max"] == 2 and observed["queue_full"] is True
    assert observed["blocked_while_full"] is True
    assert observed["frontier"] == {"status": "settled"} and observed["cutoff"] is True
    assert observed["before_later_release"] == expected[:-1]
    assert observed["physical_events"] == observed["calls"] == expected
    assert await _physical_events(observed) == expected
    assert observed["marker"]["admissions"] == 2 and observed["marker"]["attempts"] >= 3
    assert observed["final_settlement"] == {"status": "settled"}
    assert observed["drops_after_marker_admission"] == observed["drops_before"] == 0
    assert observed["forced_drop_delta"] == 1 and observed["drops_after"] == 1
    assert observed["writer"]["alive"] is True


@pytest.mark.parametrize(
    ("scenario", "admitted", "queue_full", "drop_delta", "queue_size"),
    [
        ("fatal-before-admission", False, True, 2, 2),
        ("fatal-after-admission", True, False, 1, 2),
    ],
)
# Layer: integration
async def test_fatal_daemon_wakes_frontier_without_restart_or_optional_escalation(
    tmp_path: Path, record_property, scenario: str, admitted: bool, queue_full: bool, drop_delta: int, queue_size: int,
) -> None:
    observed = await _run_probe(tmp_path, scenario, record_property)
    expected_error = {
        "status": "error",
        "error": {
            "type": "RuntimeError",
            "message": WRITER_ERROR,
            "cause_type": "ValueError",
            "cause_message": "controlled fatal log writer failure",
        },
    }
    assert observed["frontier"] == observed["second_settlement"] == expected_error
    assert observed["queue_full"] is queue_full
    assert observed["admitted_before_failure"] is admitted
    assert observed["marker"]["admissions"] == int(admitted)
    assert observed["same_writer"] is True
    assert observed["writer"]["name"] == "orket-log-writer" and observed["writer"]["alive"] is False
    assert observed["fatal_thread"]["thread_name"] == "orket-log-writer"
    assert observed["fatal_thread"]["error"]["type"] == "ValueError"
    assert observed["fatal_thread"]["error"]["message"] == "controlled fatal log writer failure"
    assert observed["optional_after_dead"] == {"status": "accepted"}
    assert observed["drops_after_optional"] - observed["drops_before_optional"] == drop_delta
    assert observed["queue_size_after_optional"] == queue_size
    assert observed["calls"] == ["fatal-first"] and observed["physical_events"] == []
    assert await _physical_events(observed) == []
