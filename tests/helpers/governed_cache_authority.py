"""Held-read fixtures for governed cache authority capture controls."""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import aiosqlite

from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    namespace_resource_id_for_run,
    publish_resource_snapshot,
)
from orket.core.contracts import AttemptRecord
from orket.core.domain import LeaseStatus
from orket.core.domain.execution import ExecutionTurn, ToolCall
from tests.helpers.operation_binding import (
    ATTEMPT_ID,
    ISSUE,
    ROLE,
    RUN_ID,
    captured_destination,
    context,
    control_plane_state,
    operation_id,
    proposal,
)
from tests.helpers.turn_artifacts import execute_executor_dispatch_fixture

__test__ = False


def _dump(record: Any) -> Any:
    return None if record is None else record.model_dump(mode="json")


async def authority_state(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    base = await control_plane_state(case)
    repository = case.service.execution_repository
    steps = []
    for attempt in base["attempts"]:
        rows = await repository.list_step_records(attempt_id=attempt["attempt_id"])
        steps.extend(_dump(row) for row in rows)
    run = await repository.get_run_record(run_id=RUN_ID)
    configuration = None
    resource = None
    if run is not None:
        configuration = await case.service.publication.repository.get_resolved_configuration_snapshot(
            snapshot_id=run.configuration_snapshot_id
        )
        resource = await case.service.publication.repository.get_latest_resource_record(
            resource_id=namespace_resource_id_for_run(run=run)
        )
    return {
        **base,
        "steps": sorted(steps, key=lambda row: (row["attempt_id"], row["step_id"])),
        "configuration": _dump(configuration),
        "resource": _dump(resource),
    }


def _file_evidence(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    content = path.read_bytes()
    return {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}


async def physical_call_files(case, operation_path: Path) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    selected = await captured_destination(case)
    paths = {
        "operation": operation_path,
        "receipt": selected.file_path("protocol_receipts.log"),
        "effect": case.workspace / "agent_output" / "out.txt",
    }
    return {
        name: await asyncio.to_thread(_file_evidence, path)
        for name, path in paths.items()
    }


def hold_operation_read(monkeypatch, target: Path) -> SimpleNamespace:  # type: ignore[no-untyped-def]
    original = Path.read_text
    hold = SimpleNamespace(
        entered=threading.Event(),
        release=threading.Event(),
        finished=threading.Event(),
        expired=False,
        worker=None,
        reads=0,
    )

    def held(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if path == target and not hold.entered.is_set():
            hold.worker = threading.get_ident()
            hold.reads += 1
            hold.entered.set()
            hold.expired = not hold.release.wait(0.8)
            try:
                return original(path, *args, **kwargs)
            finally:
                hold.finished.set()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", held)
    return hold


def _turn() -> ExecutionTurn:
    proposed = proposal()
    return ExecutionTurn(
        timestamp=None,
        role=ROLE,
        issue_id=ISSUE,
        content="",
        tool_calls=[ToolCall(tool=proposed["tool"], args=dict(proposed["args"]))],
    )


async def _dispatch(case, turn: ExecutionTurn) -> ExecutionTurn:  # type: ignore[no-untyped-def]
    return await execute_executor_dispatch_fixture(
        case.executor,
        turn=turn,
        toolbox=case.toolbox,
        context=context(),
        issue=case.issue,
    )


def start_held_dispatch(case, monkeypatch, target: Path) -> SimpleNamespace:  # type: ignore[no-untyped-def]
    admissions: list[tuple[str, str]] = []
    original_begin = case.service.begin_execution

    async def observed_begin(**kwargs):  # type: ignore[no-untyped-def]
        run, attempt = await original_begin(**kwargs)
        admissions.append((run.run_id, attempt.attempt_id))
        return run, attempt

    monkeypatch.setattr(case.service, "begin_execution", observed_begin)
    hold = hold_operation_read(monkeypatch, target)
    turn = _turn()
    task = asyncio.create_task(_dispatch(case, turn))
    return SimpleNamespace(
        admissions=admissions,
        caller_thread=threading.get_ident(),
        hold=hold,
        task=task,
        turn=turn,
    )


async def wait_for_hold(admitted: SimpleNamespace) -> None:
    assert await asyncio.to_thread(admitted.hold.entered.wait, 0.5)
    assert admitted.admissions == [(RUN_ID, ATTEMPT_ID)]
    assert admitted.hold.worker != admitted.caller_thread
    assert admitted.hold.reads == 1
    assert not admitted.hold.expired
    assert not admitted.task.done()


async def release_and_join(admitted: SimpleNamespace) -> object:
    admitted.hold.release.set()
    gathered = asyncio.gather(admitted.task, return_exceptions=True)
    try:
        outcome = (await asyncio.wait_for(asyncio.shield(gathered), 10.0))[0]
    finally:
        admitted.hold.release.set()
        if not gathered.done():
            admitted.task.cancel()
            await asyncio.wait_for(asyncio.shield(gathered), 10.0)
        native_finished = await asyncio.to_thread(admitted.hold.finished.wait, 1.0)
        assert native_finished and admitted.task.done()
    return outcome


async def run_dispatch(case) -> tuple[ExecutionTurn, object]:  # type: ignore[no-untyped-def]
    turn = _turn()
    task = asyncio.create_task(_dispatch(case, turn))
    outcome = (await asyncio.gather(task, return_exceptions=True))[0]
    return turn, outcome


async def _delete_configuration(case, seeded) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    async with aiosqlite.connect(case.database) as connection:
        cursor = await connection.execute(
            "DELETE FROM resolved_configuration_snapshots WHERE snapshot_id = ?",
            (seeded.run.configuration_snapshot_id,),
        )
        await connection.commit()
    assert cursor.rowcount == 1
    return {"deleted_snapshot_id": seeded.run.configuration_snapshot_id}


async def _add_unresolved_sibling(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    sibling = f"{operation_id()}-sibling"
    await case.service.prepare_dispatch(
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
        step_id=sibling,
        tool_name="read_file",
        tool_args={"path": "agent_output/sibling.txt"},
        binding=None,
        operation_id=sibling,
    )
    return {"sibling_step_id": sibling}


async def _revoke_lease(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    state = await control_plane_state(case)
    lease = state["lease"]
    assert lease is not None
    revoked = await case.service.publication.publish_lease(
        lease_id=lease["lease_id"],
        resource_id=lease["resource_id"],
        holder_ref=lease["holder_ref"],
        lease_epoch=lease["lease_epoch"],
        publication_timestamp="2099-01-01T00:00:01+00:00",
        expiry_basis="authority-capture-test-revocation",
        status=LeaseStatus.REVOKED,
        cleanup_eligibility_rule=lease["cleanup_eligibility_rule"],
        granted_timestamp=lease["granted_timestamp"],
        last_confirmed_observation=lease["last_confirmed_observation"],
        source_reservation_id=lease["source_reservation_id"],
    )
    return {"lease": _dump(revoked)}


async def _drift_resource(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    run = await case.service.execution_repository.get_run_record(run_id=RUN_ID)
    assert run is not None
    resource_id = namespace_resource_id_for_run(run=run)
    current = await case.service.publication.repository.get_latest_resource_record(
        resource_id=resource_id
    )
    assert current is not None
    drifted = await case.service.publication.publish_resource(
        resource_id=current.resource_id,
        resource_kind=current.resource_kind,
        namespace_scope=f"{current.namespace_scope}:drift",
        ownership_class=current.ownership_class,
        current_observed_state=current.current_observed_state,
        last_observed_timestamp="2099-01-01T00:00:02+00:00",
        cleanup_authority_class=current.cleanup_authority_class,
        provenance_ref=current.provenance_ref,
        reconciliation_status=current.reconciliation_status,
        orphan_classification=current.orphan_classification,
    )
    return {"resource": _dump(drifted)}


async def _write_run_namespace(case, namespace_scope: str):  # type: ignore[no-untyped-def]
    repository = case.service.execution_repository
    run = await repository.get_run_record(run_id=RUN_ID)
    assert run is not None
    payload = run.model_dump(mode="json")
    payload["namespace_scope"] = namespace_scope
    async with aiosqlite.connect(case.database) as connection:
        cursor = await connection.execute(
            "UPDATE control_plane_runs SET payload_json = ? WHERE run_id = ?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), RUN_ID),
        )
        await connection.commit()
    assert cursor.rowcount == 1
    mutated = await repository.get_run_record(run_id=RUN_ID)
    assert mutated is not None and mutated.namespace_scope == namespace_scope
    return mutated


async def _drift_namespace(
    case, *, publication_timestamp: str,
) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    run = await _write_run_namespace(case, "turn-tool:captured-namespace-drift")
    state = await control_plane_state(case)
    current = state["lease"]
    assert current is not None
    lease = await case.service.publication.publish_lease(
        lease_id=current["lease_id"],
        resource_id=namespace_resource_id_for_run(run=run),
        holder_ref=current["holder_ref"],
        lease_epoch=current["lease_epoch"],
        publication_timestamp=publication_timestamp,
        expiry_basis=current["expiry_basis"],
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule=current["cleanup_eligibility_rule"],
        granted_timestamp=current["granted_timestamp"],
        last_confirmed_observation=current["last_confirmed_observation"],
        source_reservation_id=current["source_reservation_id"],
    )
    resource = await publish_resource_snapshot(
        publication=case.service.publication,
        run=run,
        lease=lease,
    )
    return {"run": _dump(run), "lease": _dump(lease), "resource": _dump(resource)}


async def _advance_attempt(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    repository = case.service.execution_repository
    current = await repository.get_attempt_record(attempt_id=ATTEMPT_ID)
    assert current is not None
    payload = current.model_dump(mode="json", exclude={"state_revision"})
    payload.update({"attempt_id": f"{RUN_ID}:attempt:0002", "attempt_ordinal": 2})
    other = await repository.save_attempt_record(record=AttemptRecord.model_validate(payload))
    run = await repository.get_run_record(run_id=RUN_ID)
    assert run is not None
    advanced = await repository.save_run_record(
        record=run.model_copy(update={"current_attempt_id": other.attempt_id})
    )
    return {"run": _dump(advanced), "attempt": _dump(other)}


async def _corrupt_final_truth(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    truth = await case.service.publication.repository.get_final_truth(run_id=RUN_ID)
    assert truth is not None
    payload = truth.model_dump(mode="json")
    payload["result_class"] = "failed"
    async with aiosqlite.connect(case.database) as connection:
        cursor = await connection.execute(
            "UPDATE final_truth_records SET payload_json = ? WHERE final_truth_record_id = ?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), truth.final_truth_record_id),
        )
        await connection.commit()
    assert cursor.rowcount == 1
    return {"final_truth_record_id": truth.final_truth_record_id, "result_class": "failed"}


async def close_seeded_run(case) -> None:  # type: ignore[no-untyped-def]
    await case.service.finalize_execution(
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
        authoritative_result_ref=f"turn-tool-result:{operation_id()}",
        violation_reasons=[],
        executed_step_count=1,
    )


async def mutate_authority(
    case, seeded, mutation: str, *, namespace_publication_timestamp: str | None,
) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    if mutation == "configuration_absent":
        return await _delete_configuration(case, seeded)
    if mutation == "unresolved_sibling":
        return await _add_unresolved_sibling(case)
    if mutation == "lease_revoked":
        return await _revoke_lease(case)
    if mutation == "resource_mismatch":
        return await _drift_resource(case)
    if mutation == "namespace_mismatch":
        assert namespace_publication_timestamp is not None
        return await _drift_namespace(case, publication_timestamp=namespace_publication_timestamp)
    if mutation == "current_attempt_advanced":
        return await _advance_attempt(case)
    if mutation == "final_truth_corrupt":
        return await _corrupt_final_truth(case)
    raise AssertionError(f"unknown authority mutation: {mutation}")
