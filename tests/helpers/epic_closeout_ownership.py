"""Shared finite controls for epic closeout ownership integration probes."""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.core.contracts.tool_invocation_contracts import (
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)
from orket.runtime.execution_pipeline import ExecutionPipeline
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_epic_completion_publication import _write_epic_assets

__test__ = False


def hold_sync(
    monkeypatch,
    owner: Any,
    name: str,
    *,
    predicate: Callable[..., bool] | None = None,
    failure: BaseException | None = None,
    expiry: float = 2.0,
):
    """Hold the first selected synchronous call and retain its worker observation."""
    original = getattr(owner, name)
    state = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
        expired=False, worker=None, calls=0,
    )

    def held(*args, **kwargs):
        selected = predicate is None or predicate(*args, **kwargs)
        if not selected or state.entered.is_set():
            return original(*args, **kwargs)
        state.calls += 1
        state.worker = threading.get_ident()
        state.entered.set()
        try:
            state.expired = not state.release.wait(expiry)
            if failure is not None:
                raise failure
            return original(*args, **kwargs)
        finally:
            state.finished.set()

    monkeypatch.setattr(owner, name, held)
    return state


async def wait_for_hold(state) -> None:
    entered = await asyncio.wait_for(asyncio.to_thread(state.entered.wait, 5), 6)
    if not entered:
        raise AssertionError("native hold was not entered")


async def begin_interrupt(task: asyncio.Task, *, timed: bool):
    if timed:
        waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
        await asyncio.sleep(0.05)
        return waiter
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0.05)
    return task


async def release_and_join(state, *tasks: asyncio.Future) -> list[Any]:
    state.release.set()
    native_error = None
    try:
        native_finished = await asyncio.wait_for(asyncio.to_thread(state.finished.wait, 5), 6)
    except BaseException as error:
        native_finished, native_error = False, error
    unique = list(dict.fromkeys(task for task in tasks if task is not None))
    try:
        results = await asyncio.wait_for(asyncio.gather(*unique, return_exceptions=True), 10)
    except BaseException as error:
        if native_error is not None:
            error.add_note(f"Native hold join also failed: {native_error!r}")
        raise
    if not native_finished:
        error = AssertionError("native hold did not report completion after release")
        if native_error is not None:
            error.add_note(f"Native wait failed: {native_error!r}")
        raise error
    return results


async def interrupt_observation(
    *, task, hold, timed, sqlite_path, record_property, paths=(), mutate=None, extra=None,
) -> dict[str, Any]:
    loop_thread, waiter, primary_error = threading.get_ident(), None, None
    try:
        await wait_for_hold(hold)
        if mutate is not None:
            mutate()
        waiter = await begin_interrupt(task, timed=timed)
        before = [await physical(path) for path in paths]
        active = hold.entered.is_set() and not hold.expired and not hold.finished.is_set()
        await responsive_sqlite(sqlite_path, record_property)
        prefix = {
            "active_during_sqlite": active, "expired": hold.expired,
            "loop_thread": loop_thread, "worker_thread": hold.worker,
            "task_done": task.done(), "waiter_done": waiter.done(),
            "finished_after_sqlite": hold.finished.is_set(), "physical": before,
            "extra": extra() if extra is not None else {},
        }
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            results = await release_and_join(hold, task, waiter)
        except BaseException as cleanup_error:
            if primary_error is not None:
                record_json(record_property, "held_interruption_fixture_failure", {
                    "fixture_error": type(primary_error).__name__, "fixture_text": str(primary_error),
                    "cleanup_error": type(cleanup_error).__name__, "cleanup_text": str(cleanup_error),
                    "task": settled_future(task), "waiter": settled_future(waiter),
                    "hold_calls": hold.calls, "hold_entered": hold.entered.is_set(),
                })
            if primary_error is None:
                raise
            primary_error.add_note(f"Held interruption cleanup failed: {cleanup_error!r}")
    return {
        "pre_release": prefix, "native_finished": hold.finished.is_set(),
        "result_types": result_types(results), "result_text": [str(row) for row in results],
        "physical_after": [await physical(path) for path in paths],
    }


async def complete_held_operation(
    *, task, hold, sqlite_path, record_property, paths=(), mutate=None,
) -> tuple[dict[str, Any], list[Any]]:
    loop_thread, primary_error = threading.get_ident(), None
    try:
        await wait_for_hold(hold)
        if mutate is not None:
            mutate()
        before = [await physical(path) for path in paths]
        active = hold.entered.is_set() and not hold.expired and not hold.finished.is_set()
        await responsive_sqlite(sqlite_path, record_property)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            results = await release_and_join(hold, task)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Held operation cleanup failed: {cleanup_error!r}")
    observation = {
        "active_during_sqlite": active, "expired": hold.expired,
        "loop_thread": loop_thread, "worker_thread": hold.worker,
        "finished_after_release": hold.finished.is_set(), "physical_before": before,
        "physical_after": [await physical(path) for path in paths],
        "result_types": result_types(results),
    }
    return observation, results


async def close_pipeline(pipeline, *tasks: asyncio.Future) -> None:
    try:
        if tasks:
            unique = list(dict.fromkeys(tasks))
            await asyncio.wait_for(asyncio.gather(*unique, return_exceptions=True), 10)
    finally:
        await asyncio.wait_for(pipeline.close(), 10)


def result_types(results: list[Any]) -> list[str]:
    return [type(result).__name__ for result in results]


def assert_owned(observation: dict[str, Any]) -> None:
    before = observation["pre_release"]
    assert before["active_during_sqlite"] is True
    assert before["expired"] is False
    assert before["worker_thread"] != before["loop_thread"]
    assert before["task_done"] is False
    assert before["waiter_done"] is False
    assert before["finished_after_sqlite"] is False
    assert observation["native_finished"] is True


def assert_interrupted(observation: dict[str, Any], *, timed: bool) -> None:
    names = observation["result_types"]
    if timed:
        assert "TimeoutError" in names
    else:
        assert any(name in {"CancelledError", "RuntimeExecutionCancelled"} for name in names)


def settled_future(future: asyncio.Future | None) -> dict[str, Any]:
    if future is None or not future.done():
        return {"done": False}
    if future.cancelled():
        return {"done": True, "cancelled": True, "result_type": "CancelledError"}
    error = future.exception()
    if error is not None:
        return {
            "done": True, "cancelled": False, "result_type": type(error).__name__,
            "text_prefix": str(error)[:2000],
        }
    result = future.result()
    return {
        "done": True, "cancelled": False, "result_type": type(result).__name__,
        "text_prefix": str(result)[:2000],
    }


async def physical(path: Path) -> dict[str, Any]:
    return await asyncio.to_thread(_physical, path)


def _physical(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=False)
    if not path.exists():
        return {"path": str(resolved), "exists": False, "is_file": False, "size": 0, "sha256": None}
    if not path.is_file():
        return {"path": str(resolved), "exists": True, "is_file": False, "size": 0, "sha256": None}
    content = path.read_bytes()
    return {
        "path": str(resolved), "exists": True, "is_file": True,
        "size": len(content), "sha256": hashlib.sha256(content).hexdigest(),
    }


async def read_json(path: Path) -> dict[str, Any]:
    return await asyncio.to_thread(lambda: json.loads(path.read_text(encoding="utf-8")))


async def write_json(path: Path, payload: dict[str, Any]) -> None:
    await asyncio.to_thread(_write_json, path, payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


async def write_text(path: Path, content: str) -> None:
    await asyncio.to_thread(_write_text, path, content)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def write_protocol_receipt(workspace: Path, session_id: str, *, operation_id: str = "op-1") -> Path:
    path = workspace / "observability" / session_id / "ISSUE-1" / "001_architect" / "protocol_receipts.log"
    await asyncio.to_thread(_write_protocol_receipt, path, session_id, operation_id)
    return path


def _write_protocol_receipt(path: Path, session_id: str, operation_id: str) -> None:
    manifest = build_tool_invocation_manifest(
        run_id=session_id, tool_name="write_file",
        control_plane_run_id=f"turn-tool-run:{session_id}:ISSUE-1:architect:0001",
        control_plane_attempt_id=f"turn-tool-run:{session_id}:ISSUE-1:architect:0001:attempt:0001",
        control_plane_step_id=operation_id,
        control_plane_reservation_id=(
            f"turn-tool-reservation:turn-tool-run:{session_id}:ISSUE-1:architect:0001"
        ),
        control_plane_lease_id=f"turn-tool-lease:turn-tool-run:{session_id}:ISSUE-1:architect:0001",
        control_plane_resource_id="namespace:issue:ISSUE-1",
    )
    tool_args = {"path": f"agent_output/{operation_id}.txt", "content": "ok"}
    payload = {
        "run_id": session_id, "step_id": "ISSUE-1:1", "operation_id": operation_id,
        "tool": "write_file", "tool_index": 0, "tool_args": tool_args,
        "execution_result": {"ok": True}, "tool_invocation_manifest": manifest,
        "tool_call_hash": compute_tool_call_hash(
            tool_name="write_file", tool_args=tool_args,
            tool_contract_version=str(manifest["tool_contract_version"]),
            capability_profile=str(manifest["capability_profile"]),
        ),
    }
    _write_json(path, payload)


async def protocol_construction_inputs() -> RuntimeConstructionInputs:
    captured = await RuntimeConstructionInputs.capture_async()
    environment = {**captured.environment, "ORKET_RUN_LEDGER_MODE": "protocol"}
    return replace(captured, environment=environment)


async def protocol_publication_pipeline(test_root, workspace, db_path, inputs):
    await asyncio.to_thread(_write_epic_assets, test_root, "publication_epic")
    return await asyncio.to_thread(
        ExecutionPipeline, workspace, department="core", db_path=db_path,
        config_root=test_root, construction_inputs=inputs,
    )


async def epic_closeout_state(pipeline, workspace: Path, session_id: str, source: Path, inputs) -> dict[str, Any]:
    async with pipeline.epic_publication.repository.transaction(session_id) as transaction:
        preparation = await transaction.get_preparation()
        outcome = await transaction.get_outcome()
        publication = await transaction.get()
    projection = await pipeline.run_ledger.get_run(session_id)
    events = await pipeline.run_ledger.list_events(session_id)
    receipts = await pipeline.run_ledger.list_receipts(session_id)
    run_root = workspace / "runs" / session_id
    ledger_root = await asyncio.to_thread(Path(pipeline.run_ledger.root).resolve)
    files = await asyncio.gather(*(
        physical(source), physical(run_root / "events.log"), physical(run_root / "receipts.log"),
        physical(run_root / "run_summary.json"),
    ))
    return {
        "owner": {
            "mode": pipeline.run_ledger_mode, "repository": type(pipeline.run_ledger).__name__,
            "root": str(ledger_root),
            "construction_inputs_selected": pipeline.runtime_context.construction_inputs is inputs,
        },
        "journal": {
            "preparation": _record_fields(preparation, "phase"),
            "outcome": _record_fields(outcome, "observed_at", "failure"),
            "publication": _record_fields(publication),
        },
        "ledger": _mapping_fields(projection, "status", "kind", "event_seq"),
        "events": [_mapping_fields(row, "kind", "status", "event_seq") for row in events],
        "receipts": [_mapping_fields(row, "operation_id", "tool", "event_seq") for row in receipts],
        "physical": dict(zip(("source", "events", "receipts", "summary"), files, strict=True)),
    }


def _record_fields(record, *names: str) -> dict[str, Any]:
    if record is None:
        return {"present": False}
    payload = record.model_dump(mode="json")
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    ledger = plan.get("ledger") if isinstance(plan.get("ledger"), dict) else {}
    return {"present": True, "status": ledger.get("status"), **{name: payload.get(name) for name in names}}


def _mapping_fields(payload, *names: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"present": False}
    return {"present": True, **{name: payload.get(name) for name in names}}


def record_json(record_property, name: str, payload: dict[str, Any]) -> None:
    record_property(name, json.dumps(payload, sort_keys=True, default=str))
