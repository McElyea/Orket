"""Layer: integration. Failed real publication stages cannot strand API registration drain."""
import asyncio
import json
from contextlib import AsyncExitStack

import pytest

from orket.adapters.observability import log_publication
from orket.application.services.api_event_service import ApiEventService
from orket.logging import event_subscriber_count
from tests.integration.test_api_log_handoff_lifetime import _app, _wait_for

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
EVENT = "api_failed_log_handoff"


@pytest.mark.parametrize("stage", ["main-append", "schedule", "queue-attempt"])
async def test_failed_publication_releases_registration_tokens(tmp_path, monkeypatch, record_property, stage):
    baseline = event_subscriber_count()
    failures, attempts, contexts = [], [], []
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    async with AsyncExitStack() as stack:
        owner = await _app(stack, tmp_path / "app")
        original_append = log_publication._append_line_sync
        original_schedule = loop.call_soon_threadsafe
        original_put = owner.runtime_state.event_queue.put_nowait

        def append(path, line):
            if stage == "main-append" and json.loads(line)["event"] == EVENT:
                failures.append("main-append")
                raise OSError("fixture append failure")
            return original_append(path, line)

        def schedule(callback, *args, **kwargs):
            if stage == "schedule" and args and type(args[0]) is dict and args[0].get("event") == EVENT:
                failures.append("schedule")
                raise RuntimeError("fixture scheduling failure")
            return original_schedule(callback, *args, **kwargs)

        def put(record):
            if record.get("event") == EVENT:
                attempts.append(EVENT)
                if stage == "queue-attempt":
                    failures.append("queue-attempt")
                    raise asyncio.QueueFull()
            return original_put(record)

        monkeypatch.setattr(log_publication, "_append_line_sync", append)
        monkeypatch.setattr(loop, "call_soon_threadsafe", schedule)
        monkeypatch.setattr(owner.runtime_state.event_queue, "put_nowait", put)
        observed = None
        loop.set_exception_handler(lambda _loop, context: contexts.append(context))
        try:
            try:
                await ApiEventService(tmp_path / "publisher").emit(EVENT, {})
            except OSError as exc:
                observed = exc
            if stage == "queue-attempt":
                await _wait_for(lambda: bool(contexts))
            await asyncio.wait_for(owner.close(), 3)
        finally:
            loop.set_exception_handler(previous_handler)
        assert failures == [stage] and owner.closed and event_subscriber_count() == baseline
        assert attempts == ([EVENT] if stage == "queue-attempt" else [])
        assert (type(observed) is OSError) == (stage == "main-append")
        if stage == "queue-attempt":
            assert len(contexts) == 1 and isinstance(contexts[0]["exception"], asyncio.QueueFull)
        else:
            assert contexts == []
        path = tmp_path / "publisher" / "orket.log"
        records = [json.loads(line) for line in (await asyncio.to_thread(path.read_text, encoding="utf-8")).splitlines()] if stage != "main-append" else []
        assert [record["event"] for record in records] == (
            [EVENT, "logging_subscriber_failed"] if stage == "schedule" else [EVENT] if stage == "queue-attempt" else [])
        record_property("api_log_handoff_failure", json.dumps(dict(stage=stage, failures=failures,
            attempts=attempts, closed=owner.closed, count=event_subscriber_count(), baseline=baseline,
            error_type=None if observed is None else type(observed).__name__,
            loop_errors=[type(item["exception"]).__name__ for item in contexts], records=records, path=str(path)), sort_keys=True))
