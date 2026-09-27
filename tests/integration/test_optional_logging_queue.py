"""Classified integration/contract controls for bounded queues and publication lifetime."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import sys
import threading
import time
from functools import partial
from pathlib import Path

import pytest

import orket
from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.observability import log_publication as owner
from orket.logging import dropped_log_entry_count, log_event, settle_log_write_frontier
from tests.helpers.log_process_receipts import process_readback
from tests.helpers.logging_async_opening import sqlite_observation

pytestmark = pytest.mark.asyncio
PACKAGE_ROOT = Path(orket.__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[2]
LOGGING_ORIGIN = str((PACKAGE_ROOT / "orket/adapters/observability/log_publication.py").resolve())


@pytest.mark.integration
async def test_full_optional_queue_keeps_warning_off_loop_and_releases_dropped_tokens(
    tmp_path, monkeypatch, record_property,
):
    await run_owned_thread(settle_log_write_frontier, label="optional-queue-before")
    monkeypatch.setattr(owner._log_write_queue, "maxsize", 1)
    monkeypatch.setattr(owner, "_dropped_log_entries", 0)
    entered, release = threading.Event(), threading.Event()
    warned, release_warning = threading.Event(), threading.Event()
    records, warnings, workers = [], [], []

    class Hold(logging.Handler):
        def emit(self, record):
            if record.getMessage() == "queue_blocker":
                entered.set()
                assert release.wait(5), "blocker fixture release missing"
            elif record.getMessage() == "log_write_queue_full":
                workers.append(threading.get_ident())
                warnings.append(record.orket_record)
                warned.set()
                assert release_warning.wait(5), "warning fixture release missing"

    def handoff(record, acknowledge):
        records.append(record)
        acknowledge()

    subscription = owner.subscribe_to_event_handoffs(handoff)
    handler, logger = Hold(), logging.getLogger("orket")
    logger.addHandler(handler)
    try:
        log_event("queue_blocker", {}, workspace=tmp_path)
        assert await asyncio.to_thread(entered.wait, 3)
        started = time.perf_counter()
        log_event("turn_complete", {"session_id": "partial"}, workspace=tmp_path)
        log_event("all_dropped", {}, workspace=tmp_path)
        admission_elapsed = time.perf_counter() - started
        assert 0 < admission_elapsed < 0.5
        assert dropped_log_entry_count() == 2 and subscription.pending == 2
        for _ in range(1000):
            log_event("coalesced_drop", {}, workspace=tmp_path)
        assert dropped_log_entry_count() == 1002 and subscription.pending == 2
        assert not warned.is_set()
        release.set()
        assert await asyncio.to_thread(warned.wait, 3)
        sqlite = await sqlite_observation(tmp_path / "independent.sqlite3", time.perf_counter())
        assert 0 < sqlite["elapsed"] < 0.5 and sqlite["row"] == (42,)
    finally:
        release.set()
        release_warning.set()
        await run_owned_thread(settle_log_write_frontier, label="optional-queue-after")
        await run_owned_thread(lambda: owner.settle_event_subscription(subscription), label="optional-subscription-close")
        logger.removeHandler(handler)
        handler.close()
    physical = [json.loads(line) for line in (
        await asyncio.to_thread((tmp_path / "orket.log").read_text, encoding="utf-8")).splitlines()]
    assert [record["event"] for record in physical] == ["queue_blocker", "turn_complete"]
    assert records == physical and subscription.pending == 0 and subscription.state == "closed"
    assert not await asyncio.to_thread((tmp_path / "agent_output").exists)
    assert len(warnings) == 1 and warnings[0]["data"]["dropped_log_entries"] == 1000
    assert warnings[0]["data"]["queue_max"] == 1 and workers[0] != threading.get_ident()
    record_property("optional_queue_pressure", json.dumps(dict(
        physical=physical, warnings=warnings, pending=subscription.pending, state=subscription.state,
        sqlite=sqlite, admission_elapsed=admission_elapsed, workers=workers, caller=threading.get_ident())))


@pytest.mark.contract
async def test_refused_main_admission_does_not_prevent_independent_artifact_attempt(
    tmp_path, monkeypatch, record_property,
):
    """Layer: contract. Inject only main capacity refusal; run the admitted artifact on the real daemon."""
    await run_owned_thread(settle_log_write_frontier, label="optional-main-refusal-before")
    original = owner._log_write_queue.put_nowait
    attempts, records = [], []
    before = dropped_log_entry_count()

    def refuse_main(item):
        if isinstance(item, tuple) and isinstance(item[0], owner.OptionalPublication):
            attempts.append(item[1])
            if item[1] == 0:
                raise queue.Full
        original(item)

    def handoff(record, acknowledge):
        records.append(record)
        acknowledge()

    subscription = owner.subscribe_to_event_handoffs(handoff)
    monkeypatch.setattr(owner._log_write_queue, "put_nowait", refuse_main)
    try:
        log_event("turn_complete", {"session_id": "artifact-only"}, workspace=tmp_path)
        await run_owned_thread(settle_log_write_frontier, label="optional-main-refusal-after")
    finally:
        await run_owned_thread(lambda: owner.settle_event_subscription(subscription), label="optional-main-refusal-close")
    artifact = json.loads(await asyncio.to_thread(
        (tmp_path / "agent_output/observability/runtime_events.jsonl").read_text, encoding="utf-8"))
    assert attempts == [0, 1] and dropped_log_entry_count() == before + 1
    assert not await asyncio.to_thread((tmp_path / "orket.log").exists)
    assert records == [] and subscription.pending == 0 and subscription.state == "closed"
    assert artifact["event"] == "turn_complete" and artifact["session_id"] == "artifact-only"
    record_property("optional_independent_artifact", json.dumps(dict(
        attempts=attempts, artifact=artifact, subscriber_records=records, pending=subscription.pending)))


@pytest.mark.parametrize("kind", ["handler-value", "handler-oserror", "prepare-oserror"])
@pytest.mark.integration
async def test_fatal_optional_stage_releases_queued_tokens_and_keeps_frontier_failed(tmp_path, record_property, kind):
    helper = REPO_ROOT / "tests/helpers/optional_logging_fatal_probe.py"
    result = await execute_owned_command(
        argv=[sys.executable, str(helper), str(tmp_path), kind], cwd=tmp_path,
        environment=dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONDONTWRITEBYTECODE="1",
                         PYTHONPATH=os.pathsep.join(dict.fromkeys((str(PACKAGE_ROOT), str(REPO_ROOT))))),
        timeout_seconds=12, input_data=None, stop=asyncio.Event(), output_limit_bytes=256 * 1024)
    assert result.reason == "completed" and result.returncode == 0, result.stderr
    assert result.cleanup_confirmed and result.capture_complete
    observed = json.loads(result.stdout)
    physical = json.loads(await asyncio.to_thread((tmp_path / "probe-report.json").read_text, encoding="utf-8"))
    assert observed == physical and observed["diff_ledger"]
    assert observed["pending_before"] == 2 and observed["pending_during_hold"]
    assert observed["pending_after"] == 0 and observed["state"] == "closed" and not observed["callbacks"]
    error_type = "ValueError" if kind == "handler-value" else "OSError"
    assert observed["frontier"] == dict(error=owner.LOG_WRITER_TERMINATED_ERROR,
                                       cause_type=error_type, cause_identity=True)
    assert observed["retained_identity"] and observed["same_writer"] and not observed["writer_alive"]
    assert observed["thread_errors"] == [error_type] and 0 < observed["sqlite"]["elapsed"] < 0.5
    assert observed["sqlite"]["row"] == [42]
    assert observed["logging_origin"] == LOGGING_ORIGIN
    identities = {pid: None for pid in (result.transport_pid, result.supervisor_pid, result.command_pid) if pid}
    identities[observed["pid"]] = observed["create_time"]
    processes = await run_owned_thread(partial(process_readback, identities), label="optional-fatal-process-readback")
    assert processes and all(item["status"] in {"absent", "reused"} for item in processes.values())
    record_property("optional_fatal_tokens", json.dumps(dict(observation=observed, processes=processes)))


@pytest.mark.integration
async def test_optional_append_oserror_retains_artifact_and_subscriber_attempt(tmp_path, monkeypatch, record_property):
    await run_owned_thread(settle_log_write_frontier, label="optional-append-refusal-before")
    original, attempts, records = owner._append_line_sync, [], []

    def fail_main(path, line):
        attempts.append(str(path))
        if path == tmp_path / "orket.log":
            raise OSError("fixture optional main append refusal")
        original(path, line)

    def handoff(record, acknowledge):
        records.append(record)
        acknowledge()

    subscription = owner.subscribe_to_event_handoffs(handoff)
    monkeypatch.setattr(owner, "_append_line_sync", fail_main)
    try:
        log_event("turn_complete", {"session_id": "main-refused"}, workspace=tmp_path)
        await run_owned_thread(settle_log_write_frontier, label="optional-append-refusal-after")
    finally:
        await run_owned_thread(lambda: owner.settle_event_subscription(subscription), label="optional-append-refusal-close")
    artifact_path = tmp_path / "agent_output/observability/runtime_events.jsonl"
    artifact = json.loads(await asyncio.to_thread(artifact_path.read_text, encoding="utf-8"))
    assert attempts == [str(tmp_path / "orket.log"), str(artifact_path)]
    assert len(records) == 1 and records[0]["data"]["runtime_event"] == artifact
    assert subscription.pending == 0 and subscription.state == "closed"
    assert owner._log_writer_thread.is_alive() and owner._log_writer_failure is None
    assert not await asyncio.to_thread((tmp_path / "orket.log").exists)
    record_property("optional_append_refusal", json.dumps(dict(attempts=attempts, artifact=artifact, records=records)))
