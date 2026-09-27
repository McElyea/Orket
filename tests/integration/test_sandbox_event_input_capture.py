"""Layer: integration. Hook refusal before actual SQLite/spool publication effects."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.sandbox_lifecycle_event_publisher import SandboxLifecycleEventPublisher
from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService
from orket.core.contracts.log_event_inputs import LOG_EVENT_INPUT_ERROR
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleEventRecord
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sandbox_event_ownership import event, failed_repository, spool_records

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class HookedDict(dict):
    def __init__(self, *, delay_hook=None):
        super().__init__(value="original")
        self.calls = []
        self.delay_hook = delay_hook

    def _observe(self, hook):
        self.calls.append(hook)
        if self.delay_hook == hook:
            threading.Event().wait(1)

    def __deepcopy__(self, memo):
        self._observe("deepcopy")
        return self

    def items(self):
        self._observe("items")
        return super().items()


async def publish(entrypoint, service, payload):
    if entrypoint == "publisher":
        publisher = SandboxLifecycleEventPublisher(repository=service.repository, spool_path=service.spool_path)
        return await publisher.emit(sandbox_id="sandbox-proof", created_at="2026-09-27T00:00:00+00:00",
                                    event_type="sandbox.cleanup_scheduled", payload=payload)
    selected = event("retained")
    selected.payload = payload
    return await service.emit(selected)


@pytest.mark.parametrize("entrypoint", ["service", "publisher"])
# Layer: integration
async def test_custom_deepcopy_alias_refuses_before_borrowed_repository(tmp_path, entrypoint, record_property):
    failed, attempts = await failed_repository(tmp_path), []

    class MutatingRepository:
        async def append_event(self, record):
            attempts.append(record.event_id)
            record.payload["nested"]["value"] = "repository mutation"
            await failed.append_event(record)

    service = SandboxLifecycleEventService(repository=MutatingRepository(), spool_path=tmp_path / "events.jsonl")
    custom = HookedDict()
    result, = await asyncio.gather(publish(entrypoint, service, {"nested": custom}), return_exceptions=True)
    rows = await spool_records(service.spool_path) if await asyncio.to_thread(service.spool_path.exists) else []
    record_property("hook_calls", json.dumps(custom.calls))
    record_property("repository_attempts", json.dumps(attempts))
    record_property("retained_rows", json.dumps(rows))
    assert isinstance(result, TypeError) and str(result) == LOG_EVENT_INPUT_ERROR
    assert custom.calls == [] and attempts == [] and rows == []
    assert custom["value"] == "original"


@pytest.mark.parametrize("entrypoint, hook", [("service", "deepcopy"), ("publisher", "items")])
# Layer: integration
async def test_blocking_input_hooks_are_not_invoked(tmp_path, entrypoint, hook, record_property):
    database = tmp_path / "events.db"
    service = SandboxLifecycleEventService(repository=AsyncSandboxLifecycleRepository(database),
                                           spool_path=tmp_path / "events.jsonl")
    custom = HookedDict(delay_hook=hook)
    started = time.perf_counter()
    response = asyncio.create_task(sqlite_response(tmp_path / "responsive.db", record_property, started))
    result = asyncio.create_task(publish(entrypoint, service, {"nested": custom}))
    elapsed, outcome = await asyncio.gather(response, result, return_exceptions=True)
    record_property("hook_calls", json.dumps(custom.calls))
    assert isinstance(elapsed, float) and elapsed < 0.5
    assert isinstance(outcome, TypeError) and str(outcome) == LOG_EVENT_INPUT_ERROR
    assert custom.calls == []
    assert not await asyncio.to_thread(database.exists)
    assert not await asyncio.to_thread(service.spool_path.exists)


def unsupported(case):
    if case == "cycle":
        value = []
        value.append(value)
        return value
    if case == "dict_subclass":
        return HookedDict()
    if case == "list_subclass":
        return type("CustomList", (list,), {})([1])
    if case == "str_subclass":
        return type("CustomString", (str,), {})("custom")
    return {"nan": float("nan"), "infinity": float("inf"), "path": Path("custom"),
            "nonstring_key": {1: "value"}, "set": {1}, "bytes": b"value"}[case]


@pytest.mark.parametrize("entrypoint", ["service", "publisher"])
@pytest.mark.parametrize("case", ["cycle", "dict_subclass", "list_subclass", "str_subclass", "nan", "infinity",
                                  "path", "nonstring_key", "set", "bytes"])
# Layer: integration
async def test_unsupported_value_refuses_before_publication(tmp_path, entrypoint, case):
    database = tmp_path / "events.db"
    service = SandboxLifecycleEventService(repository=AsyncSandboxLifecycleRepository(database),
                                           spool_path=tmp_path / "events.jsonl")
    with pytest.raises(TypeError, match=LOG_EVENT_INPUT_ERROR):
        await publish(entrypoint, service, {"nested": unsupported(case)})
    assert not await asyncio.to_thread(database.exists)
    assert not await asyncio.to_thread(service.spool_path.exists)


@pytest.mark.parametrize("sink", ["primary", "fallback"])
# Layer: integration
async def test_supported_builtins_keep_json_identity_and_values(tmp_path, sink):
    repository = (AsyncSandboxLifecycleRepository(tmp_path / "events.db") if sink == "primary"
                  else await failed_repository(tmp_path))
    publisher = SandboxLifecycleEventPublisher(repository=repository, spool_path=tmp_path / "events.jsonl")
    payload = {"values": [None, True, False, 7, -4, 1.5, "text", {"tuple": (1, {"two": 2})}]}
    assert await publisher.emit(sandbox_id="sandbox-proof", created_at="2026-09-27T00:00:00+00:00",
                                event_type="sandbox.cleanup_scheduled", payload=payload) == sink
    expected_id = publisher._event_id(sandbox_id="sandbox-proof", created_at="2026-09-27T00:00:00+00:00",
                                       event_type="sandbox.cleanup_scheduled", payload=payload)
    if sink == "primary":
        retained, = await repository.list_events()
        row = retained.model_dump(mode="json")
    else:
        row = (await spool_records(tmp_path / "events.jsonl"))[0]["record"]
    assert row["payload"] == json.loads(json.dumps(payload))
    assert row["event_id"] == expected_id


# Layer: integration
async def test_record_subclass_refuses_without_copy_or_dump_hook(tmp_path):
    calls = []

    class CustomRecord(SandboxLifecycleEventRecord):
        def model_copy(self, **kwargs):
            calls.append("copy")
            return super().model_copy(**kwargs)

        def model_dump(self, **kwargs):
            calls.append("dump")
            return super().model_dump(**kwargs)

    database = tmp_path / "events.db"
    selected = CustomRecord(**event("retained").model_dump())
    service = SandboxLifecycleEventService(repository=AsyncSandboxLifecycleRepository(database),
                                           spool_path=tmp_path / "events.jsonl")
    with pytest.raises(TypeError, match=LOG_EVENT_INPUT_ERROR):
        await service.emit(selected)
    assert calls == [] and not await asyncio.to_thread(database.exists)


# Layer: integration
async def test_invalid_retained_value_refuses_without_retry_or_deletion(tmp_path):
    database = tmp_path / "events.db"
    service = SandboxLifecycleEventService(repository=AsyncSandboxLifecycleRepository(database),
                                           spool_path=tmp_path / "events.jsonl")
    selected = event("retained").model_dump()
    selected["payload"] = {"value": float("nan")}
    original = json.dumps({"record": selected, "retry_count": 1}) + "\n"
    await asyncio.to_thread(service.spool_path.write_text, original, encoding="utf-8")
    with pytest.raises(TypeError, match=LOG_EVENT_INPUT_ERROR):
        await service.replay_spool()
    assert await asyncio.to_thread(service.spool_path.read_text, encoding="utf-8") == original
    assert not await asyncio.to_thread(database.exists)
