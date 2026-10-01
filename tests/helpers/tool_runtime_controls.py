"""Actual native writes and async cleanup controls for the tool runtime boundary."""
from __future__ import annotations

import asyncio
import threading
import time
from functools import partial

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.tools.runtime import ToolRuntimeExecutor
from orket.application.services.toolbox import ToolBox
from tests.helpers.lifetime_finalizer_native import AppendHold


def tool_failure(kind):
    if kind in {"success", "returned-exception"}:
        return None
    failure = {"OSError": OSError("native tool failure after write"),
        "CancelledError": asyncio.CancelledError("native tool cancellation after write"),
        "SystemExit": SystemExit(69), "KeyboardInterrupt": KeyboardInterrupt("native tool fatal after write"),
        "BaseException": BaseException("native tool base failure after write")}[kind]
    failure.__cause__ = LookupError("original tool failure cause")
    return failure


class NativeToolHold:
    def __init__(self, root, failure, value):
        self.root, self.failure, self.value = root, failure, value
        self.entered, self.release, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.calls, self.worker, self.expired = 0, None, False
        self.args, self.context = None, None

    def run(self, args, *, context):
        self.calls += 1
        self.worker, self.args, self.context = threading.get_ident(), args, context
        (self.root / "tool-effect.bin").write_bytes(args["content"])
        self.entered.set()
        try:
            self.expired = not self.release.wait(10)
            assert not self.expired, "native tool hold was not released"
            if self.failure is not None:
                raise self.failure
            return self.value
        finally:
            self.finished.set()


class AsyncToolHold:
    def __init__(self, root, value):
        self.root, self.value = root, value
        self.entered, self.release, self.finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        self.cleanup_entered = asyncio.Event()
        self.cancellations, self.calls, self.task = [], 0, None
        self.args, self.context = None, None

    async def run(self, args, *, context):
        self.calls += 1
        self.task, self.args, self.context = asyncio.current_task(), args, context
        self.entered.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError as failure:
            self.cancellations.append(failure)
            self.cleanup_entered.set()
            await self.release.wait()
            await run_owned_thread(partial((self.root / "tool-effect.bin").write_bytes, args["content"]),
                                   label="fixture-async-tool-cleanup")
            self.finished.set()
            raise
        await run_owned_thread(partial((self.root / "tool-effect.bin").write_bytes, args["content"]),
                               label="fixture-async-tool-result")
        self.finished.set()
        return self.value


async def arrange_tool(root, route, kind, stop, monkeypatch):
    failure = tool_failure(kind)
    value = BaseException("ordinary returned tool value") if kind == "returned-exception" else 37
    args, context = {"content": b"real tool effect"}, {"nested": {"value": "borrowed"}, "tool_name": "held_tool"}
    timeout = 0.05 if stop in {"deadline", "deadline-repeated", "cancel-then-deadline"} else 10
    if route == "toolbox":
        hold = AppendHold("card_nomination", failure)
        hold.install(monkeypatch)
        toolbox = await asyncio.to_thread(partial(ToolBox, None, str(root), [], db_path=str(root / "cards.sqlite3")))
        args = {"issue_id": "retained-nomination"}
        context["tool_timeout_seconds"] = timeout
        operation = toolbox.execute("nominate_card", args, context=context)
        name = "nominate_card"
    else:
        hold = AsyncToolHold(root, value) if route == "async" else NativeToolHold(root, failure, value)
        operation = ToolRuntimeExecutor().invoke(hold.run, args, context=context, workspace=root,
                                                 tool_name="held_tool", tool_timeout_seconds=timeout)
        name = "held_tool"
    return hold, operation, failure, value, args, context, name


async def entered(hold):
    if isinstance(hold, AsyncToolHold):
        await asyncio.wait_for(hold.entered.wait(), 3)
    else:
        assert await asyncio.to_thread(hold.entered.wait, 3), "native tool did not start"
        assert hold.worker != threading.get_ident()


async def interrupt(active, hold, stop):
    waiter = active
    if stop in {"deadline", "deadline-repeated"}:
        await asyncio.sleep(.1)
    if stop in {"cancel", "cancel-then-deadline", "deadline-repeated"}:
        active.cancel("first tool caller interruption")
        await asyncio.sleep(0)
        active.cancel("repeated tool caller interruption")
    if stop == "cancel-then-deadline":
        await asyncio.sleep(.1)
    if stop == "abandoned-waiter":
        waiter = asyncio.create_task(asyncio.wait_for(active, .02))
        started = time.perf_counter()
        while active.cancelling() == 0 and not active.done() and time.perf_counter() - started < 2:
            await asyncio.wait({waiter}, timeout=.005)
        assert active.cancelling() == 1, "external deadline did not interrupt the held invocation"
        waiter.cancel("external waiter abandonment")
        started = time.perf_counter()
        while not waiter.done() and active.cancelling() < 2 and time.perf_counter() - started < 2:
            await asyncio.wait({waiter}, timeout=.005)
        assert waiter.done() or active.cancelling() >= 2, "external waiter cancellation was not observed"
    if isinstance(hold, AsyncToolHold) and stop != "none":
        await asyncio.wait_for(hold.cleanup_entered.wait(), 3)
    return waiter


async def settle(active, waiter, hold):
    hold.release.set()
    await asyncio.wait_for(asyncio.gather(active, waiter, return_exceptions=True), 10)
    if isinstance(hold, AsyncToolHold):
        if hold.task is not None:
            await asyncio.wait_for(asyncio.gather(hold.task, return_exceptions=True), 3)
    elif hold.entered.is_set():
        assert await asyncio.to_thread(hold.finished.wait, 3)


def assert_outcome(outcome, hold, failure, value, kind, stop, name, args, context, route):
    if failure is not None:
        if isinstance(failure, OSError):
            assert outcome == {"ok": False, "error": str(failure)}
        else:
            assert outcome is failure
    elif stop == "deadline":
        assert outcome == {"ok": False, "error": "tool_timeout", "tool": name}
    elif stop != "none":
        assert type(outcome) is asyncio.CancelledError
        first_args = () if stop in {"deadline-repeated", "abandoned-waiter"} else ("first tool caller interruption",)
        assert outcome.args == first_args
    else:
        assert outcome["ok"] is True and outcome["result"] is value
    if route != "toolbox":
        assert hold.args is args and hold.context is not context
        assert hold.context["nested"] is context["nested"], "trusted borrowed nested context policy changed"
    if isinstance(hold, AsyncToolHold):
        assert len(hold.cancellations) == int(stop != "none")
    assert hold.calls == 1 and hold.finished.is_set()
    return {"outcome_type": type(outcome).__name__, "result_policy": True,
        "native_identity": failure is not None and not isinstance(failure, OSError),
        "returned_exception_value": kind == "returned-exception",
        "async_cancellations": len(hold.cancellations) if isinstance(hold, AsyncToolHold) else None}
