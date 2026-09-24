"""Matched integration probes for epic closeout native-operation ownership."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.services.epic_preparation_service import EpicPreparationService
from orket.runtime.evidence import protocol_receipt_materializer as receipt_module
from orket.runtime.evidence.protocol_receipt_materializer import materialize_protocol_receipts
from orket.runtime.execution import epic_run_result_boundary as result_boundary_module
from orket.runtime.summary import run_summary_io as summary_io_module
from orket.runtime.summary.run_summary import (
    build_degraded_run_summary_payload,
    generate_run_summary_for_finalize,
    write_run_summary_artifact,
)
from tests.helpers.epic_closeout_ownership import (
    assert_interrupted,
    assert_owned,
    close_pipeline,
    complete_held_operation,
    epic_closeout_state,
    hold_sync,
    interrupt_observation,
    physical,
    protocol_construction_inputs,
    protocol_publication_pipeline,
    read_json,
    record_json,
    write_json,
    write_protocol_receipt,
    write_text,
)
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_STARTED, _ENDED = "2026-09-23T10:00:00+00:00", "2026-09-23T10:00:01+00:00"


def _summary_payload(session_id: str) -> dict:
    return build_degraded_run_summary_payload(
        run_id=session_id, status="incomplete", failure_reason=None, artifacts={},
    )


@pytest.mark.parametrize("timed", [False, True], ids=["cancel", "timeout"])
# Layer: integration
async def test_protocol_receipt_discovery_owns_interruption(
    tmp_path, monkeypatch, record_property, timed,
) -> None:
    workspace, session_id = tmp_path / "workspace", f"receipt-{timed}"
    receipt_path = await write_protocol_receipt(workspace, session_id)
    repo = AsyncProtocolRunLedgerRepository(workspace)
    hold = hold_sync(monkeypatch, receipt_module, "_protocol_receipt_files")
    task = asyncio.create_task(materialize_protocol_receipts(
        workspace=workspace, session_id=session_id, run_ledger=repo,
    ))
    observation = await interrupt_observation(
        task=task, hold=hold, timed=timed, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(receipt_path,),
    )
    observation["events"] = await repo.list_events(session_id)
    observation["receipts"] = await repo.list_receipts(session_id)
    record_json(record_property, "receipt_discovery_observation", observation)
    assert_owned(observation)
    assert_interrupted(observation, timed=timed)
    assert observation["events"] == [] and observation["receipts"] == []
    assert observation["physical_after"] == observation["pre_release"]["physical"]


# Layer: integration
async def test_protocol_receipt_discovery_healthy_real_file(tmp_path, record_property) -> None:
    workspace, session_id = tmp_path / "workspace", "receipt-healthy"
    receipt_path = await write_protocol_receipt(workspace, session_id)
    repo = AsyncProtocolRunLedgerRepository(workspace)
    result = await materialize_protocol_receipts(workspace=workspace, session_id=session_id, run_ledger=repo)
    observation = {
        "result": result, "events": await repo.list_events(session_id),
        "receipts": await repo.list_receipts(session_id), "physical": await physical(receipt_path),
    }
    record_json(record_property, "receipt_healthy_observation", observation)
    assert result["materialized_receipts"] == 1
    assert [row["kind"] for row in observation["events"]] == ["tool_call", "operation_result"]
    assert len(observation["receipts"]) == 1 and observation["physical"]["is_file"]


@pytest.mark.parametrize("timed", [False, True], ids=["cancel", "timeout"])
# Layer: integration
async def test_run_summary_receipt_read_owns_interruption(tmp_path, monkeypatch, record_property, timed) -> None:
    session_id = f"summary-read-{timed}"
    receipt_path = tmp_path / "observability" / session_id / "ISSUE-1" / "001_coder" / "protocol_receipts.log"
    await write_text(receipt_path, json.dumps({"tool": "workspace.read"}) + "\n")
    hold = hold_sync(monkeypatch, summary_io_module, "_receipt_paths")
    task = asyncio.create_task(generate_run_summary_for_finalize(
        workspace=tmp_path, run_id=session_id, status="incomplete", failure_reason=None,
        started_at=_STARTED, ended_at=_ENDED, artifacts={},
    ))
    observation = await interrupt_observation(
        task=task, hold=hold, timed=timed, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(receipt_path,),
    )
    record_json(record_property, "summary_receipt_observation", observation)
    assert_owned(observation)
    assert_interrupted(observation, timed=timed)
    assert observation["physical_after"] == observation["pre_release"]["physical"]


# Layer: integration
async def test_summary_write_captures_payload_before_held_mkdir(tmp_path, monkeypatch, record_property) -> None:
    session_id, payload = "summary-capture", _summary_payload("summary-capture")
    target = tmp_path / "runs" / session_id / "run_summary.json"
    hold = hold_sync(monkeypatch, Path, "mkdir", predicate=lambda path, *a, **k: Path(path) == target.parent)
    task = asyncio.create_task(write_run_summary_artifact(root=tmp_path, session_id=session_id, payload=payload))
    observation, _ = await complete_held_operation(
        task=task, hold=hold, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(target,),
        mutate=lambda: payload["tools_used"].append("mutated.after.admission"),
    )
    emitted = await read_json(target)
    observation["emitted"] = emitted
    record_json(record_property, "summary_payload_capture_observation", observation)
    assert observation["active_during_sqlite"] and not observation["expired"]
    assert observation["worker_thread"] != observation["loop_thread"]
    assert observation["finished_after_release"] is True
    assert emitted["tools_used"] == []


# Layer: integration
async def test_summary_write_drains_repeated_cancellation(tmp_path, monkeypatch, record_property) -> None:
    session_id, payload = "summary-cancel", _summary_payload("summary-cancel")
    target = tmp_path / "runs" / session_id / "run_summary.json"
    hold = hold_sync(monkeypatch, Path, "mkdir", predicate=lambda path, *a, **k: Path(path) == target.parent)
    task = asyncio.create_task(write_run_summary_artifact(root=tmp_path, session_id=session_id, payload=payload))
    observation = await interrupt_observation(
        task=task, hold=hold, timed=False, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(target,),
        mutate=lambda: payload["tools_used"].append("mutated.after.admission"),
    )
    observation["emitted"] = await read_json(target) if observation["physical_after"][0]["is_file"] else None
    record_json(record_property, "summary_cancel_observation", observation)
    assert_owned(observation)
    assert_interrupted(observation, timed=False)
    assert observation["emitted"] is not None and observation["emitted"]["tools_used"] == []


# Layer: integration
async def test_summary_write_late_oserror_preserves_preparation_mapping(
    tmp_path, monkeypatch, record_property,
) -> None:
    session_id, payload = "summary-fault", _summary_payload("summary-fault")
    target = tmp_path / "runs" / session_id / "run_summary.json"
    hold = hold_sync(
        monkeypatch, Path, "mkdir", predicate=lambda path, *a, **k: Path(path) == target.parent,
        failure=OSError("held-summary-publication-fault"),
    )

    async def publish():
        return await write_run_summary_artifact(root=tmp_path, session_id=session_id, payload=payload)

    task = asyncio.create_task(EpicPreparationService._invoke("materialize run summary", publish))
    observation = await interrupt_observation(
        task=task, hold=hold, timed=False, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(target,),
    )
    record_json(record_property, "summary_fault_observation", observation)
    assert_owned(observation)
    assert "OrketInfrastructureError" in observation["result_types"]
    assert any("held-summary-publication-fault" in text for text in observation["result_text"])
    assert observation["physical_after"][0]["exists"] is False


# Layer: integration
async def test_summary_read_and_write_healthy_physical_artifact(tmp_path, record_property) -> None:
    session_id = "summary-healthy"
    receipt_path = tmp_path / "observability" / session_id / "ISSUE-1/001_coder/protocol_receipts.log"
    await write_text(receipt_path, json.dumps({"tool": "workspace.read"}) + "\n")
    payload = await generate_run_summary_for_finalize(
        workspace=tmp_path, run_id=session_id, status="incomplete", failure_reason=None,
        started_at=_STARTED, ended_at=_ENDED, artifacts={},
    )
    target = await write_run_summary_artifact(root=tmp_path, session_id=session_id, payload=payload)
    observation = {"physical": await physical(target), "emitted": await read_json(target)}
    record_json(record_property, "summary_write_healthy_observation", observation)
    assert observation["physical"]["is_file"] and observation["emitted"] == payload
    assert payload["tools_used"] == ["workspace.read"]


# Layer: integration
async def test_artifact_provenance_stat_owns_cancellation(
    test_root, workspace, db_path, tmp_path, monkeypatch, record_property,
) -> None:
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    artifact = workspace / "agent_output" / "provenance.txt"
    await write_text(artifact, "owned provenance\n")
    hold = hold_sync(monkeypatch, pipeline, "_artifact_produced_at")
    task = asyncio.create_task(pipeline._artifact_provenance_entry_from_log_pair(
        run_id="provenance-cancel", operation_id="op-provenance",
        start={"issue_id": "ISSUE-1", "role_name": "coder", "turn_index": 1,
               "tool_args": {"path": "agent_output/provenance.txt", "content": "owned provenance\n"}},
        workspace=workspace,
    ))
    try:
        observation = await interrupt_observation(
            task=task, hold=hold, timed=False, sqlite_path=tmp_path / "responsive.sqlite3",
            record_property=record_property, paths=(artifact,),
        )
        record_json(record_property, "provenance_stat_observation", observation)
    finally:
        hold.release.set()
        await close_pipeline(pipeline, task)
    assert_owned(observation)
    assert_interrupted(observation, timed=False)
    assert observation["physical_after"] == observation["pre_release"]["physical"]


# Layer: integration
async def test_packet1_telemetry_discovery_owns_timeout(
    test_root, workspace, db_path, tmp_path, monkeypatch, record_property,
) -> None:
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    response_path = (
        workspace / "observability" / "runtime-timeout" / "ISSUE-1" / "001_coder" / "model_response_raw.json"
    )
    await write_json(response_path, {"provider_backend": "controlled", "model": "fixture-model"})
    hold = hold_sync(monkeypatch, pipeline, "_packet1_model_response_paths_at")
    task = asyncio.create_task(pipeline._resolve_packet1_runtime_telemetry_at(
        run_id="runtime-timeout", workspace=workspace))
    try:
        observation = await interrupt_observation(
            task=task, hold=hold, timed=True, sqlite_path=tmp_path / "responsive.sqlite3",
            record_property=record_property, paths=(response_path,),
        )
        record_json(record_property, "runtime_telemetry_observation", observation)
    finally:
        hold.release.set()
        await close_pipeline(pipeline, task)
    assert_owned(observation)
    assert_interrupted(observation, timed=True)
    assert observation["physical_after"] == observation["pre_release"]["physical"]


# Layer: integration
async def test_packet2_log_exists_runs_off_loop(
    test_root, workspace, db_path, tmp_path, monkeypatch, record_property,
) -> None:
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    log_path = workspace / "orket.log"
    await write_text(log_path, json.dumps({
        "event": "turn_corrective_reprompt",
        "data": {"session_id": "exists-held", "issue_id": "ISSUE-1", "turn_index": 1,
                 "contract_reasons": ["held-exists"]},
    }) + "\n")
    hold = hold_sync(monkeypatch, Path, "exists", predicate=lambda path: Path(path) == log_path)
    task = asyncio.create_task(pipeline._resolve_packet2_repair_entries_at(
        run_id="exists-held", workspace=workspace))
    try:
        observation, results = await complete_held_operation(
            task=task, hold=hold, sqlite_path=tmp_path / "responsive.sqlite3",
            record_property=record_property, paths=(log_path,),
        )
        observation["result"] = results[0] if results and isinstance(results[0], list) else None
        record_json(record_property, "packet2_exists_observation", observation)
    finally:
        hold.release.set()
        await close_pipeline(pipeline, task)
    assert observation["active_during_sqlite"] and not observation["expired"]
    assert observation["worker_thread"] != observation["loop_thread"]
    assert observation["finished_after_release"] is True
    assert observation["result"] and observation["result"][0]["repair_id"] == "repair:ISSUE-1:1:corrective_reprompt"


# Layer: integration
async def test_packet2_log_exists_healthy_result(test_root, workspace, db_path, record_property) -> None:
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    try:
        result = await pipeline._resolve_packet2_repair_entries_at(
            run_id="exists-healthy", workspace=workspace)
        observation = {"result": result, "physical": await physical(workspace / "orket.log")}
        record_json(record_property, "packet2_exists_healthy_observation", observation)
    finally:
        await close_pipeline(pipeline)
    assert result == []


async def _cancel_composed_receipt(
    test_root, workspace, db_path, session_id, source, inputs, tmp_path, monkeypatch, record_property,
) -> tuple[dict, dict]:
    pipeline = await protocol_publication_pipeline(test_root, workspace, db_path, inputs)

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)

    cancellation_started = asyncio.Event()
    shield_observation = result_boundary_module.shield_observation

    async def observed_cancellation(awaitable):
        cancellation_started.set()
        return await shield_observation(awaitable)

    hold, task = None, None
    try:
        before = await epic_closeout_state(pipeline, workspace, session_id, source, inputs)
        record_json(record_property, "composed_epic_receipt_before", before)
        monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_fixture)
        monkeypatch.setattr(result_boundary_module, "shield_observation", observed_cancellation)
        hold = hold_sync(monkeypatch, receipt_module, "_protocol_receipt_files")
        task = asyncio.create_task(pipeline.run_epic("publication_epic", build_id="build", session_id=session_id))
        observation = await interrupt_observation(
            task=task, hold=hold, timed=False, sqlite_path=tmp_path / "responsive.sqlite3",
            record_property=record_property,
            paths=(source, workspace / "runs" / session_id / "events.log",
                   workspace / "runs" / session_id / "receipts.log"),
            extra=lambda: {"cancellation_observation_started": cancellation_started.is_set()},
        )
        observation["state_after_cancel"] = await epic_closeout_state(
            pipeline, workspace, session_id, source, inputs)
        record_json(record_property, "composed_epic_receipt_cancelled_prefix", observation)
        return before, observation
    finally:
        if hold is not None:
            hold.release.set()
        await close_pipeline(pipeline, *([task] if task is not None else []))


async def _recover_composed_receipt(
    test_root, workspace, db_path, session_id, source, inputs, monkeypatch, record_property,
) -> dict:
    restarted = await protocol_publication_pipeline(test_root, workspace, db_path, inputs)
    dispatches = 0

    async def forbidden_dispatch(**_kwargs):
        nonlocal dispatches
        dispatches += 1
        raise AssertionError("retained preparation recovery redispatched workload")

    monkeypatch.setattr(restarted.orchestrator, "execute_epic", forbidden_dispatch)
    try:
        recovered = await restarted.run_epic("publication_epic", build_id="build", session_id=session_id)
        recovery = {
            "recovered_observation": recovered.observation, "recovery_dispatches": dispatches,
            "state": await epic_closeout_state(restarted, workspace, session_id, source, inputs),
        }
        record_json(record_property, "composed_epic_receipt_recovery", recovery)
        return recovery
    finally:
        await close_pipeline(restarted)


# Layer: integration
async def test_run_epic_receipt_cancellation_retains_pending_phase_and_recovers(
    test_root, workspace, db_path, tmp_path, monkeypatch, record_property,
) -> None:
    session_id = "epic-receipt-cancel"
    inputs = await protocol_construction_inputs()
    source = await write_protocol_receipt(workspace, session_id, operation_id="composed-op")
    before, observation = await _cancel_composed_receipt(
        test_root, workspace, db_path, session_id, source, inputs, tmp_path, monkeypatch, record_property)
    recovery = await _recover_composed_receipt(
        test_root, workspace, db_path, session_id, source, inputs, monkeypatch, record_property)
    cancelled, recovered = observation["state_after_cancel"], recovery["state"]
    assert_owned(observation)
    assert_interrupted(observation, timed=False)
    assert observation["pre_release"]["extra"]["cancellation_observation_started"] is False
    assert before["owner"] == {
        "mode": "protocol", "repository": "AsyncProtocolRunLedgerRepository",
        "root": str(workspace), "construction_inputs_selected": True,
    }
    assert before["journal"]["preparation"]["present"] is False and before["ledger"]["present"] is False
    assert before["physical"]["source"]["is_file"] and not before["physical"]["events"]["exists"]
    assert cancelled["journal"]["preparation"]["phase"] == 1
    assert cancelled["journal"]["outcome"]["present"] and not cancelled["journal"]["publication"]["present"]
    assert cancelled["ledger"]["status"] == "running" and cancelled["receipts"] == []
    assert cancelled["physical"]["events"]["is_file"] and not cancelled["physical"]["receipts"]["exists"]
    assert cancelled["physical"]["summary"]["exists"] is False and recovered["owner"] == before["owner"]
    assert recovery["recovery_dispatches"] == 0 and recovery["recovered_observation"] == "published"
    assert recovered["journal"]["preparation"]["phase"] == 5 and recovered["ledger"]["status"] == "done"
    assert recovered["journal"]["outcome"]["present"] and recovered["journal"]["publication"]["present"]
    assert len(recovered["receipts"]) == 1 and recovered["physical"]["receipts"]["is_file"]
    assert recovered["physical"]["summary"]["is_file"]
