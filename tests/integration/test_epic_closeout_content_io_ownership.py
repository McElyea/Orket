"""Content-level ownership controls for epic closeout file operations."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.services.epic_preparation_service import EpicPreparationService
from orket.runtime.evidence.protocol_receipt_materializer import materialize_protocol_receipts
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
    hold_sync,
    interrupt_observation,
    physical,
    read_json,
    record_json,
    write_protocol_receipt,
    write_text,
)
from tests.integration.test_epic_completion_publication import publication_pipeline

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_STARTED = "2026-09-23T10:00:00+00:00"
_ENDED = "2026-09-23T10:00:01+00:00"


def _summary_payload(session_id: str) -> dict:
    return build_degraded_run_summary_payload(
        run_id=session_id, status="incomplete", failure_reason=None, artifacts={},
    )


def _target_read(path: Path):
    return lambda candidate, *args, **kwargs: Path(candidate) == path


@pytest.mark.parametrize("timed", [False, True], ids=["cancel", "timeout"])
# Layer: integration
async def test_protocol_receipt_content_read_owns_interruption(
    tmp_path, monkeypatch, record_property, timed,
) -> None:
    workspace, session_id = tmp_path / "workspace", f"receipt-content-{timed}"
    receipt_path = await write_protocol_receipt(workspace, session_id)
    repo = AsyncProtocolRunLedgerRepository(workspace)
    hold = hold_sync(monkeypatch, Path, "read_text", predicate=_target_read(receipt_path))
    task = asyncio.create_task(materialize_protocol_receipts(
        workspace=workspace, session_id=session_id, run_ledger=repo,
    ))
    observation = await interrupt_observation(
        task=task, hold=hold, timed=timed, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(receipt_path,),
    )
    observation["events"] = await repo.list_events(session_id)
    observation["receipts"] = await repo.list_receipts(session_id)
    record_json(record_property, "receipt_content_observation", observation)
    assert_owned(observation)
    assert_interrupted(observation, timed=timed)
    assert observation["events"] == [] and observation["receipts"] == []
    assert observation["physical_after"] == observation["pre_release"]["physical"]


@pytest.mark.parametrize("timed", [False, True], ids=["cancel", "timeout"])
# Layer: integration
async def test_run_summary_receipt_content_read_owns_interruption(
    tmp_path, monkeypatch, record_property, timed,
) -> None:
    session_id = f"summary-content-{timed}"
    receipt_path = tmp_path / "observability" / session_id / "ISSUE-1/001_coder/protocol_receipts.log"
    await write_text(receipt_path, json.dumps({"tool": "workspace.read"}) + "\n")
    hold = hold_sync(monkeypatch, Path, "read_text", predicate=_target_read(receipt_path))
    task = asyncio.create_task(generate_run_summary_for_finalize(
        workspace=tmp_path, run_id=session_id, status="incomplete", failure_reason=None,
        started_at=_STARTED, ended_at=_ENDED, artifacts={},
    ))
    observation = await interrupt_observation(
        task=task, hold=hold, timed=timed, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(receipt_path,),
    )
    record_json(record_property, "summary_content_observation", observation)
    assert_owned(observation)
    assert_interrupted(observation, timed=timed)
    assert observation["physical_after"] == observation["pre_release"]["physical"]


# Layer: integration
async def test_run_summary_captures_nested_artifacts_before_content_read(
    tmp_path, monkeypatch, record_property,
) -> None:
    session_id = "summary-nested-capture"
    receipt_path = tmp_path / "observability" / session_id / "ISSUE-1/001_coder/protocol_receipts.log"
    await write_text(receipt_path, json.dumps({"tool": "workspace.read"}) + "\n")
    artifacts = {"packet1_facts": {
        "primary_work_artifact_output": {"id": "agent_output/A.txt", "kind": "artifact"},
    }}
    hold = hold_sync(monkeypatch, Path, "read_text", predicate=_target_read(receipt_path))
    task = asyncio.create_task(generate_run_summary_for_finalize(
        workspace=tmp_path, run_id=session_id, status="incomplete", failure_reason=None,
        started_at=_STARTED, ended_at=_ENDED, artifacts=artifacts,
    ))
    observation, results = await complete_held_operation(
        task=task, hold=hold, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(receipt_path,),
        mutate=lambda: artifacts["packet1_facts"]["primary_work_artifact_output"].update(
            id="agent_output/B.txt"),
    )
    observation["summary"] = results[0] if isinstance(results[0], dict) else None
    record_json(record_property, "summary_nested_capture_observation", observation)
    assert observation["active_during_sqlite"] and not observation["expired"]
    assert observation["worker_thread"] != observation["loop_thread"]
    assert observation["finished_after_release"] is True
    assert observation["physical_before"][0]["is_file"] is True
    assert observation["physical_after"] == observation["physical_before"]
    assert observation["summary"]["truthful_runtime_packet1"]["provenance"]["primary_output_id"] == (
        "agent_output/A.txt"
    )


# Layer: integration
async def test_run_summary_content_read_preserves_unicode_line_separator_token(
    tmp_path, record_property,
) -> None:
    session_id, tool_name = "summary-unicode-separator", "workspace\u2028read"
    receipt_path = tmp_path / "observability" / session_id / "ISSUE-1/001_coder/protocol_receipts.log"
    await write_text(receipt_path, json.dumps({"tool": tool_name}, ensure_ascii=False) + "\n")
    summary = await generate_run_summary_for_finalize(
        workspace=tmp_path, run_id=session_id, status="incomplete", failure_reason=None,
        started_at=_STARTED, ended_at=_ENDED, artifacts={},
    )
    observation = {"physical": await physical(receipt_path), "tools_used": summary["tools_used"]}
    record_json(record_property, "summary_unicode_separator_observation", observation)
    assert observation["physical"]["is_file"] and observation["tools_used"] == [tool_name]


# Layer: integration
async def test_protocol_receipt_malformed_json_is_strict_without_ledger_writes(
    tmp_path, record_property,
) -> None:
    workspace, session_id = tmp_path / "workspace", "receipt-malformed"
    receipt_path = workspace / "observability" / session_id / "ISSUE-1/001_coder/protocol_receipts.log"
    await write_text(receipt_path, "{malformed-json\n")
    repo = AsyncProtocolRunLedgerRepository(workspace)
    with pytest.raises(json.JSONDecodeError) as caught:
        await materialize_protocol_receipts(workspace=workspace, session_id=session_id, run_ledger=repo)
    observation = {
        "error_type": type(caught.value).__name__, "error": str(caught.value),
        "events": await repo.list_events(session_id), "receipts": await repo.list_receipts(session_id),
        "physical": await physical(receipt_path),
    }
    record_json(record_property, "receipt_malformed_observation", observation)
    assert observation["error_type"] == "JSONDecodeError"
    assert observation["events"] == [] and observation["receipts"] == []
    assert observation["physical"]["is_file"] is True


# Layer: integration
async def test_run_summary_receipt_malformed_json_is_strict(tmp_path, record_property) -> None:
    session_id = "summary-malformed"
    receipt_path = tmp_path / "observability" / session_id / "ISSUE-1/001_coder/protocol_receipts.log"
    await write_text(receipt_path, "{malformed-json\n")
    with pytest.raises(json.JSONDecodeError) as caught:
        await generate_run_summary_for_finalize(
            workspace=tmp_path, run_id=session_id, status="incomplete", failure_reason=None,
            started_at=_STARTED, ended_at=_ENDED, artifacts={},
        )
    observation = {
        "error_type": type(caught.value).__name__, "error": str(caught.value),
        "physical": await physical(receipt_path),
    }
    record_json(record_property, "summary_malformed_observation", observation)
    assert observation["error_type"] == "JSONDecodeError" and observation["physical"]["is_file"]


# Layer: integration
async def test_artifact_provenance_tolerates_malformed_rows_and_retains_valid_tail(
    test_root, workspace, db_path, record_property,
) -> None:
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    try:
        session_id, operation_id = "provenance-tolerant", "valid-tail"
        receipt_path = await write_protocol_receipt(workspace, session_id, operation_id=operation_id)
        output_path = workspace / "agent_output" / f"{operation_id}.txt"
        await write_text(output_path, "retained valid output\n")
        valid_tail = await asyncio.to_thread(receipt_path.read_text, encoding="utf-8")
        await write_text(receipt_path, "{malformed-json\n[]\n" + valid_tail)
        entries = await pipeline._resolve_artifact_provenance_entries(
            run_id=session_id, workspace=workspace,
        )
        observation = {
            "entries": entries, "receipt": await physical(receipt_path),
            "output": await physical(output_path),
        }
        record_json(record_property, "provenance_tolerant_rows_observation", observation)
    finally:
        await close_pipeline(pipeline)
    assert len(observation["entries"]) == 1
    assert observation["entries"][0]["artifact_path"] == f"agent_output/{operation_id}.txt"
    assert observation["receipt"]["is_file"] and observation["output"]["is_file"]


# Layer: integration
async def test_artifact_provenance_content_read_owns_cancellation(
    test_root, workspace, db_path, tmp_path, monkeypatch, record_property,
) -> None:
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    hold, task = None, None
    try:
        session_id = "provenance-content-cancel"
        receipt_path = await write_protocol_receipt(workspace, session_id)
        hold = hold_sync(monkeypatch, Path, "read_text", predicate=_target_read(receipt_path))
        task = asyncio.create_task(pipeline._resolve_artifact_provenance_entries(
            run_id=session_id, workspace=workspace,
        ))
        observation = await interrupt_observation(
            task=task, hold=hold, timed=False, sqlite_path=tmp_path / "responsive.sqlite3",
            record_property=record_property, paths=(receipt_path,),
        )
        record_json(record_property, "provenance_content_observation", observation)
    finally:
        if hold is not None:
            hold.release.set()
        await close_pipeline(pipeline, *([task] if task is not None else []))
    assert_owned(observation)
    assert_interrupted(observation, timed=False)
    assert observation["physical_after"] == observation["pre_release"]["physical"]


# Layer: integration
async def test_summary_content_write_drains_cancellation_and_captures_payload(
    tmp_path, monkeypatch, record_property,
) -> None:
    session_id, payload = "summary-write-content-cancel", _summary_payload("summary-write-content-cancel")
    target = tmp_path / "runs" / session_id / "run_summary.json"
    hold = hold_sync(monkeypatch, Path, "write_text", predicate=_target_read(target))
    task = asyncio.create_task(write_run_summary_artifact(root=tmp_path, session_id=session_id, payload=payload))
    observation = await interrupt_observation(
        task=task, hold=hold, timed=False, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(target,),
        mutate=lambda: payload["tools_used"].append("mutated.after.admission"),
    )
    observation["emitted"] = await read_json(target) if observation["physical_after"][0]["is_file"] else None
    record_json(record_property, "summary_content_write_cancel_observation", observation)
    assert_owned(observation)
    assert_interrupted(observation, timed=False)
    assert observation["emitted"] is not None and observation["emitted"]["tools_used"] == []


# Layer: integration
async def test_summary_content_write_late_oserror_preserves_failure(
    tmp_path, monkeypatch, record_property,
) -> None:
    session_id, payload = "summary-write-content-fault", _summary_payload("summary-write-content-fault")
    target = tmp_path / "runs" / session_id / "run_summary.json"
    hold = hold_sync(
        monkeypatch, Path, "write_text", predicate=_target_read(target),
        failure=OSError("held-summary-content-write-fault"),
    )

    async def publish():
        return await write_run_summary_artifact(root=tmp_path, session_id=session_id, payload=payload)

    task = asyncio.create_task(EpicPreparationService._invoke("materialize run summary", publish))
    observation = await interrupt_observation(
        task=task, hold=hold, timed=False, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property, paths=(target,),
    )
    record_json(record_property, "summary_content_write_fault_observation", observation)
    assert_owned(observation)
    assert "OrketInfrastructureError" in observation["result_types"]
    assert any("held-summary-content-write-fault" in text for text in observation["result_text"])
    assert observation["physical_after"][0]["exists"] is False


# Layer: integration
async def test_summary_content_write_healthy_physical_artifact(tmp_path, record_property) -> None:
    session_id, payload = "summary-write-content-healthy", _summary_payload("summary-write-content-healthy")
    target = await write_run_summary_artifact(root=tmp_path, session_id=session_id, payload=payload)
    observation = {"physical": await physical(target), "emitted": await read_json(target)}
    record_json(record_property, "summary_content_write_healthy_observation", observation)
    assert observation["physical"]["is_file"] and observation["emitted"] == payload
