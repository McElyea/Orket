"""Inputs and native call holds for evidence ownership integration controls."""
from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

from orket.core.domain.outward_runs import OutwardRunRecord
from tests.helpers.runtime_verification_hold import settle, sqlite_response, wait_entered


async def timeout_evidence_while_held(task, hold, database, record_property):
    """Observe actual deadline cancellation before releasing the native hold."""
    await wait_entered(hold)
    assert not hold.finished.is_set() and task.cancelling() == 0
    started = time.perf_counter()
    waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
    try:
        while task.cancelling() == 0 and not task.done() and time.perf_counter() - started < 2:
            await asyncio.wait({waiter}, timeout=0.005)
        record_property("deadline_cancellation_requests", task.cancelling())
        record_property("deadline_observed_seconds", time.perf_counter() - started)
        assert task.cancelling() == 1, "wait_for deadline did not interrupt the held caller"
        assert await sqlite_response(database, record_property) < 0.5
        assert not waiter.done() and not task.done(), "timeout escaped an admitted native operation"
        assert not hold.finished.is_set(), "native hold settled before explicit release"
        hold.release.set()
        try:
            await waiter
        except TimeoutError:
            pass
        else:
            raise AssertionError("timeout was lost")
    finally:
        hold.release.set()
        await asyncio.gather(waiter, return_exceptions=True)


async def settle_evidence(task, hold):
    """Drain the attempted operation, then close handles abandoned by failing openings."""
    try:
        await settle(task, hold)
    finally:
        hold.release.set()
        try:
            if hold.entered.is_set():
                assert await asyncio.to_thread(hold.finished.wait, 3), "held evidence operation did not settle"
        finally:
            # Product closure assertions run before this fixture-only recovery.
            pending = [stream for stream in getattr(hold, "streams", ()) if not stream.closed]
            outcomes = await asyncio.gather(*(asyncio.to_thread(stream.close) for stream in pending),
                                            return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    raise outcome


def hold_native_call(monkeypatch, target, name, selected=lambda *_args, **_kwargs: True):
    """Delay a selected actual call before delegating; record its native settlement."""
    original = getattr(target, name)
    hold = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                           thread=None, expired=False)

    def invoke(*args, **kwargs):
        if hold.entered.is_set() or not selected(*args, **kwargs):
            return original(*args, **kwargs)
        hold.thread = threading.get_ident()
        hold.entered.set()
        try:
            hold.expired = not hold.release.wait(5)
            assert not hold.expired, "evidence native call was not released"
            return original(*args, **kwargs)
        finally:
            hold.finished.set()

    monkeypatch.setattr(target, name, invoke)
    return hold


def model_evidence_inputs(root):
    run = OutwardRunRecord(run_id="native-run", namespace="native-owner", status="running",
        submitted_at="2026-09-28T00:00:00Z", current_turn=1, max_turns=1,
        task={"description": "Native evidence proof", "instruction": "Propose one file."}, policy_overrides={})
    call = {"tool": "write_file", "args": {"path": "proposal-only.txt", "content": "original content"}}
    response = SimpleNamespace(content="", raw={"provider_name": "fixture-provider", "model": "fixture-model",
        "usage": {"prompt_tokens": 5, "completion_tokens": 2}, "tool_calls": [call]})
    return {"workspace_root": root, "run": run, "messages": [{"role": "user", "content": "original prompt"}],
        "runtime_context": {"native_tools": [{"function": {"name": "original-tool"}}]},
        "response": response, "tool_call": call, "result": "tool_call_extracted", "error_type": None,
        "pii_fields": (), "evidence_scope": "b" * 64}


def model_evidence_directory(root, scope="b" * 64):
    directory = root / "workspace/native-owner/runs/native-run"
    return directory if scope is None else directory / "model_attempts" / scope
