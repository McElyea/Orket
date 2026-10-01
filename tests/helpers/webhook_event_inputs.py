"""Bounded native webhook publication and independent physical observations."""
import asyncio
import json
import sqlite3
import threading
from copy import deepcopy
from types import SimpleNamespace

from orket.adapters.observability.logging_context import selected_logging
from orket.application.services import gitea_webhook_runtime


def review_payload():
    return {"event_id": "capture-delivery", "pull_request": {"number": 7},
            "review": {"user": {"login": "reviewer"}, "state": "changes_requested", "body": "Fix validation"},
            "repository": {"name": "repo", "owner": {"login": "org"}}}


async def records(path):
    def read():
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_bytes().splitlines()]
    return await asyncio.to_thread(read)


async def database_snapshot(path):
    def read():
        if not path.exists():
            return None
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
            return {"delivery": connection.execute("SELECT event_id FROM webhook_event_dedupe").fetchall(),
                    "cycles": connection.execute("SELECT cycle_count FROM pr_review_cycles").fetchall(),
                    "failures": connection.execute("SELECT reviewer, reason FROM review_failures").fetchall()}
    return await asyncio.to_thread(read)


def hold_event(monkeypatch, runtime, target):
    state = SimpleNamespace(entered=threading.Event(), unblock=threading.Event(), finished=threading.Event(),
        claimed=False, expired=False, worker=None, selection=None, payload=None, expected=None, native_error=None)
    actual_owner, actual_event = gitea_webhook_runtime.run_owned_thread, runtime._log_event

    async def observe_event(name, payload):
        if name == target and not state.claimed:
            state.payload, state.expected = payload, deepcopy(payload)
        return await actual_event(name, payload)

    async def held_owner(operation, *, label):
        if label != "webhook-event-publication" or state.payload is None or state.claimed:
            return await actual_owner(operation, label=label)
        state.claimed = True

        def invoke():
            state.worker, state.selection = threading.get_ident(), selected_logging()
            state.entered.set()
            try:
                state.expired = not state.unblock.wait(5)
                if state.expired:
                    raise TimeoutError("webhook event fixture hold expired")
                return operation()
            except BaseException as error:
                state.native_error = error
                raise
            finally:
                state.finished.set()
        return await actual_owner(invoke, label=label)

    monkeypatch.setattr(runtime, "_log_event", observe_event)
    monkeypatch.setattr(gitea_webhook_runtime, "run_owned_thread", held_owner)
    return state


async def admitted(state, runtime, request):
    assert await asyncio.to_thread(state.entered.wait, 5), "actual event worker was not admitted"
    assert state.worker != threading.get_ident() and state.selection is runtime.logging_context
    assert runtime.active_request_count == 1 and not request.done() and not runtime.client.is_closed


async def interrupt(request, stop):
    if stop == "cancel":
        request.cancel("first")
        await asyncio.sleep(0)
        request.cancel("second")
        await asyncio.sleep(0)
        assert not request.done()


async def release(state, request):
    state.unblock.set()
    outcome, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 7)
    return outcome


def assert_settled(state, runtime):
    assert state.finished.is_set() and not state.expired
    assert runtime.active_request_count == runtime.active_background_task_count == 0


async def assert_record(root, event, expected):
    row, = [row for row in await records(root / "orket.log") if row["event"] == event]
    assert {key: value for key, value in row["data"].items() if key != "runtime_event"} == expected
    assert row["timestamp"].endswith("-07:00")


class HookedName(str):
    calls = 0

    def __hash__(self):
        self.calls += 1
        return super().__hash__()


class HookedPayload(dict):
    calls = 0

    def __iter__(self):
        self.calls += 1
        return super().__iter__()


class HookedValue:
    calls = 0

    def __str__(self):
        self.calls += 1
        return "conversion ran"


def refused_values(kind):
    if kind == "name":
        hook = HookedName("webhook-refusal")
        return hook, {"value": "ordinary"}, hook
    if kind == "container":
        hook = HookedPayload(value="ordinary")
        return "webhook-refusal", hook, hook
    hook = HookedValue()
    if kind == "value":
        return "webhook-refusal", {"value": hook}, hook
    cycle = []
    cycle.append(cycle)
    return "webhook-refusal", {"value": cycle}, hook
