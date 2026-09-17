"""Real-store controls for immutable run admission and native writer races."""
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager

import aiosqlite
import pytest
from pydantic import ValidationError

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
    ControlPlaneExecutionConflictError,
)
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import (
    KernelActionControlPlaneError,
    KernelActionControlPlaneService,
)
from orket.core.contracts import RunRecord
from orket.core.domain import RunState

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def admitted_run():
    return RunRecord(
        run_id="immutable-run", workload_id="workload", workload_version="v1",
        policy_snapshot_id="policy", policy_digest="sha256:policy",
        configuration_snapshot_id="config", configuration_digest="sha256:config",
        creation_timestamp="2026-09-14T00:00:00Z", admission_decision_receipt_ref="admission",
        namespace_scope="scope:original", lifecycle_state=RunState.ADMITTED, current_attempt_id="attempt-1",
    )


@asynccontextmanager
async def writer(db, borrowed):
    if borrowed:
        async with SQLiteControlPlaneTransactions(db)() as transaction:
            yield transaction.execution
    else:
        yield AsyncControlPlaneExecutionRepository(db)


@pytest.mark.parametrize("borrowed", [False, True], ids=["standalone", "transaction"])
@pytest.mark.parametrize("field", [
    "contract_version", "workload_id", "workload_version", "policy_snapshot_id", "policy_digest",
    "configuration_snapshot_id", "configuration_digest", "creation_timestamp", "admission_decision_receipt_ref", "namespace_scope",
])
# Layer: integration
async def test_admission_fields_are_immutable_in_both_write_scopes(tmp_path, borrowed, field):
    db = tmp_path / "authority.sqlite3"
    original = admitted_run()
    async with writer(db, borrowed) as repository:
        original = await repository.save_run_record(record=original)
    async with writer(db, borrowed) as repository:
        expected = ValidationError if field == "contract_version" else ControlPlaneExecutionConflictError
        message = "unsupported control-plane contract_version" if field == "contract_version" else "E_CONTROL_PLANE_RUN_AUTHORITY_CONFLICT"
        with pytest.raises(expected, match=message):
            await repository.save_run_record(record=original.model_copy(update={field: "changed:" + field}))
    assert await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id=original.run_id) == original


@pytest.mark.parametrize("borrowed", [False, True], ids=["standalone", "transaction"])
# Layer: integration
async def test_admission_retry_and_execution_state_updates_remain_available(tmp_path, borrowed):
    db = tmp_path / "authority.sqlite3"
    original = admitted_run()
    async with writer(db, borrowed) as repository:
        original = await repository.save_run_record(record=original)
        assert await repository.save_run_record(record=original) == original
        updated = await repository.save_run_record(record=original.model_copy(
            update={"lifecycle_state": RunState.EXECUTING, "current_attempt_id": "attempt-2"}))
        assert updated.state_revision == original.state_revision + 1
        assert updated.lifecycle_state is RunState.EXECUTING and updated.current_attempt_id == "attempt-2"
    assert await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id=original.run_id) == updated


@pytest.mark.parametrize("changed_before_wait", [False, True], ids=["original-input", "conflicting-input"])
# Layer: integration
async def test_writer_compares_the_same_input_snapshot_it_persists(tmp_path, monkeypatch, changed_before_wait):
    db = tmp_path / "input-snapshot.sqlite3"
    repository = AsyncControlPlaneExecutionRepository(db)
    original = await repository.save_run_record(record=admitted_run())
    incoming = original.model_copy(update={"namespace_scope": "scope:changed"} if changed_before_wait else {})
    waiting = asyncio.Event()
    execute = aiosqlite.Connection.execute

    def observed_execute(connection, sql, *args, **kwargs):
        if sql == "BEGIN IMMEDIATE":
            waiting.set()
        return execute(connection, sql, *args, **kwargs)

    async with SQLiteControlPlaneTransactions(db)():
        monkeypatch.setattr(aiosqlite.Connection, "execute", observed_execute)
        task = asyncio.create_task(repository.save_run_record(record=incoming))
        try:
            await asyncio.wait_for(waiting.wait(), timeout=10)
            incoming.namespace_scope = original.namespace_scope if changed_before_wait else "scope:changed"
        except (asyncio.CancelledError, TimeoutError):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
    if changed_before_wait:
        with pytest.raises(ControlPlaneExecutionConflictError):
            await task
    else:
        assert await task == original
    assert await repository.get_run_record(run_id=original.run_id) == original


NATIVE_WRITER = """
import asyncio, json, sys
from pathlib import Path
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository, ControlPlaneExecutionConflictError
from orket.core.contracts import RunRecord
async def main():
    db, gate, payload = sys.argv[1:]
    repository = AsyncControlPlaneExecutionRepository(db)
    record = RunRecord.model_validate_json(payload)
    print('ready', flush=True)
    while not await asyncio.to_thread(Path(gate).exists):
        await asyncio.sleep(0.01)
    try:
        await repository.save_run_record(record=record)
        print(json.dumps({'result':'admitted','namespace':record.namespace_scope}), flush=True)
    except ControlPlaneExecutionConflictError:
        print(json.dumps({'result':'refused','namespace':record.namespace_scope}), flush=True)
asyncio.run(main())
"""


# Layer: integration
async def test_competing_native_admissions_preserve_one_immutable_winner(tmp_path):
    db, gate = tmp_path / "race.sqlite3", tmp_path / "go"
    await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id="none")
    children = []
    try:
        for namespace in ("scope:first", "scope:second"):
            record = admitted_run().model_copy(update={"namespace_scope": namespace})
            children.append(await asyncio.create_subprocess_exec(
                sys.executable, "-c", NATIVE_WRITER, str(db), str(gate), record.model_dump_json(),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            ))
        ready = await asyncio.wait_for(asyncio.gather(*(p.stdout.readline() for p in children)), timeout=20)
        assert ready == [b"ready\n", b"ready\n"] or ready == [b"ready\r\n", b"ready\r\n"]
        await asyncio.to_thread(gate.touch)
        completed = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in children)), timeout=20)
        assert all(p.returncode == 0 for p in children), completed
        results = [json.loads(stdout) for stdout, _ in completed]
        assert sorted(row["result"] for row in results) == ["admitted", "refused"]
        winner = next(row["namespace"] for row in results if row["result"] == "admitted")
        assert (await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id="immutable-run")).namespace_scope == winner
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
    assert all(child.returncode is not None for child in children)


# Layer: integration
async def test_kernel_admission_refuses_missing_historical_namespace_without_backfill(tmp_path):
    db = tmp_path / "kernel.sqlite3"
    execution = AsyncControlPlaneExecutionRepository(db)
    service = KernelActionControlPlaneService(execution_repository=execution,
        publication=ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(db)))
    request = {"contract_version": "kernel_api/v1", "session_id": "session", "trace_id": "trace",
               "proposal": {"proposal_type": "action.tool_call", "payload": {"tool_name": "write_file"}}}
    response = {"proposal_digest": "a" * 64, "decision_digest": "b" * 64,
                "event_digest": "c" * 64, "admission_decision": {"decision": "ACCEPT_TO_UNIFY"}}
    ledger = [{"event_type": "admission.decided", "created_at": "2026-09-14T00:00:00Z", "event_digest": "c" * 64}]
    run, _ = await service.record_admission(request=request, response=response, ledger_items=ledger)
    async with aiosqlite.connect(db) as connection:
        await connection.execute("UPDATE control_plane_runs SET payload_json=json_set(payload_json,'$.namespace_scope',NULL) WHERE run_id=?", (run.run_id,))
        await connection.commit()
    before = await execution.get_run_record(run_id=run.run_id)
    with pytest.raises(KernelActionControlPlaneError, match="namespace scope mismatch"):
        await service.record_admission(request=request, response=response, ledger_items=ledger)
    assert await execution.get_run_record(run_id=run.run_id) == before
