"""Layer: integration. Optional capture refuses hooks and binds deferred native work."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.observability.logging_context import bind_logging, prepare_logging
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import log_event, settle_log_write_frontier, subscribe_to_events, unsubscribe_from_events
from tests.helpers.logging_async_opening import sqlite_observation
from tests.integration.test_api_event_input_capture import _unsupported

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("kind", [
    "opaque", "mapping-subclass", "list-subclass", "string-subclass", "key-subclass",
    "nonstring-key", "cycle-dict", "cycle-list", "nan", "infinity", "root-list",
    "event-subclass", "event-object",
])
async def test_optional_capture_refuses_before_hooks_or_publication(tmp_path, record_property, kind):
    prepared = await prepare_logging(LoggingInputs(tmp_path))
    with bind_logging(prepared):
        await run_owned_thread(settle_log_write_frontier, label="optional-refusal-before")
        hooks, handlers, subscribers = [], [], []
        event, payload = _unsupported(kind, hooks)

        class Observe(logging.Handler):
            def emit(self, record):
                handlers.append(record.name)

        handler, logger, callback = Observe(), logging.getLogger("orket"), subscribers.append
        logger.addHandler(handler)
        subscribe_to_events(callback)
        try:
            with pytest.raises(TypeError, match="^E_LOG_EVENT_INPUT_UNSUPPORTED$"):
                log_event(event, payload, workspace=tmp_path)
            await run_owned_thread(settle_log_write_frontier, label="optional-refusal-after")
        finally:
            unsubscribe_from_events(callback)
            logger.removeHandler(handler)
            handler.close()
        files = await asyncio.to_thread(lambda: list(tmp_path.iterdir()))
        assert not hooks and not handlers and not subscribers and not files
        record_property("optional_capture_refusal", json.dumps(dict(
            kind=kind, hooks=hooks, handlers=handlers, subscribers=subscribers, files=files)))


async def test_optional_relative_root_timezone_and_nested_sinks_remain_captured(
    tmp_path, monkeypatch, record_property,
):
    first, later = tmp_path / "first", tmp_path / "later"
    await asyncio.to_thread(first.mkdir)
    await asyncio.to_thread(later.mkdir)
    monkeypatch.chdir(first)
    monkeypatch.setenv("ORKET_TIMEZONE", "MST")
    prepared = await prepare_logging(LoggingInputs(first, timezone_name="MST"))
    with bind_logging(prepared):
        entered, release = threading.Event(), threading.Event()
        subscriber_records, workers = [], []
        logger = logging.getLogger("orket")

        class Hold(logging.Handler):
            def emit(self, record):
                if record.getMessage() == "turn_complete":
                    workers.append(threading.get_ident())
                    entered.set()
                    assert release.wait(5), "native handler fixture release missing"

        handler, callback = Hold(), subscriber_records.append
        logger.addHandler(handler)
        subscribe_to_events(callback)
        payload = {"session_id": "captured-session", "nested": {"values": ["captured"]}}
        try:
            log_event("turn_complete", payload, workspace=type(tmp_path)("logs"))
            assert await asyncio.to_thread(entered.wait, 3)
            payload["nested"]["values"].append("late")
            monkeypatch.chdir(later)
            monkeypatch.setenv("ORKET_TIMEZONE", "UTC")
            sqlite = await sqlite_observation(tmp_path / "independent.sqlite3", time.perf_counter())
            assert 0 < sqlite["elapsed"] < 0.5 and sqlite["row"] == (42,)
        finally:
            release.set()
            await run_owned_thread(settle_log_write_frontier, label="optional-captured-settlement")
            unsubscribe_from_events(callback)
            logger.removeHandler(handler)
            handler.close()
        record = json.loads(await asyncio.to_thread((first / "logs/orket.log").read_text, encoding="utf-8"))
        artifact = json.loads(await asyncio.to_thread(
            (first / "logs/agent_output/observability/runtime_events.jsonl").read_text, encoding="utf-8"))
        assert record["data"]["nested"]["values"] == ["captured"]
        assert record["timestamp"].endswith("-07:00")
        assert record["data"]["runtime_event"] == artifact
        assert subscriber_records == [record]
        assert not await asyncio.to_thread((later / "logs").exists)
        assert workers and workers == [workers[0]] and workers[0] != threading.get_ident()
        record_property("optional_captured_sinks", json.dumps(dict(
            record=record, artifact=artifact, subscribers=subscriber_records, sqlite=sqlite,
            caller=threading.get_ident(), workers=workers, first=str(first), later=str(later))))
