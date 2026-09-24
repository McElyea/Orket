"""High-level ownership controls for epic closeout materializer inputs.

The scope is the real materializer and selected repositories, not provider dispatch,
whole-epic capture, module globals, RuntimeContext, or arbitrary repository internals.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.core.domain.records import IssueRecord
from tests.helpers.epic_closeout_ownership import (
    close_pipeline,
    complete_held_operation,
    hold_sync,
    physical,
    protocol_construction_inputs,
    protocol_publication_pipeline,
    read_json,
    record_json,
    write_json,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_FINALIZED_AT = "2026-09-23T12:00:00+00:00"
_STARTED_AT = "2026-09-23T11:59:59+00:00"
_ISSUE_ID = "ISSUE-1"


async def _start_ledger(ledger: Any, session_id: str) -> None:
    await ledger.start_run(
        session_id=session_id,
        run_type="epic",
        run_name="closeout-input-capture",
        department="core",
        build_id="build",
    )


async def _seed_cards(cards: AsyncCardRepository, *, action: str) -> None:
    await cards.save(IssueRecord(id=_ISSUE_ID, summary="Closeout input capture", seat="standard"))
    await cards.add_transaction(_ISSUE_ID, "fixture", action)


async def _write_status_receipt(workspace: Path, session_id: str) -> Path:
    path = workspace / "observability" / session_id / _ISSUE_ID / "001_architect" / "protocol_receipts.log"
    await write_json(path, {
        "run_id": session_id,
        "step_id": f"{_ISSUE_ID}:1",
        "receipt_seq": 1,
        "operation_id": "status-a",
        "tool_index": 0,
        "tool": "update_issue_status",
        "tool_args": {"issue_id": _ISSUE_ID, "status": "done"},
        "execution_result": {"ok": True, "issue_id": _ISSUE_ID, "status": "done"},
    })
    return path


async def _repository_state(ledger: Any, cards: AsyncCardRepository, session_id: str) -> dict[str, Any]:
    events, history = await asyncio.gather(
        ledger.list_events(session_id),
        cards.get_card_history(_ISSUE_ID),
    )
    return {
        "ledger_type": type(ledger).__name__,
        "cards_type": type(cards).__name__,
        "events": events,
        "history": history,
    }


async def _prepare_case(test_root, workspace: Path, db_path: str, tmp_path: Path, session_id: str):
    inputs = await protocol_construction_inputs()
    pipeline = await protocol_publication_pipeline(test_root, workspace, db_path, inputs)
    try:
        workspace_b = tmp_path / "workspace-b"
        cards_a = pipeline.async_cards
        cards_b = AsyncCardRepository(tmp_path / "cards-b.sqlite3")
        ledger_a = pipeline.run_ledger
        ledger_b = AsyncProtocolRunLedgerRepository(workspace_b)
        await asyncio.gather(
            _seed_cards(cards_a, action="Set Status to 'done'"),
            _seed_cards(cards_b, action="Set Status to 'blocked'"),
            _start_ledger(ledger_a, session_id),
            _start_ledger(ledger_b, session_id),
        )
        receipt = await _write_status_receipt(workspace, session_id)
        return {
            "pipeline": pipeline,
            "workspace_a": workspace,
            "workspace_b": workspace_b,
            "cards_a": cards_a,
            "cards_b": cards_b,
            "ledger_a": ledger_a,
            "ledger_b": ledger_b,
            "receipt": receipt,
        }
    except BaseException:
        await close_pipeline(pipeline)
        raise


def _mutate_case(case: dict[str, Any], artifacts: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pipeline = case["pipeline"]
    pipeline.workspace = case["workspace_b"]
    pipeline.async_cards = case["cards_b"]
    pipeline.run_ledger = case["ledger_b"]
    artifacts["packet1_facts"]["primary_work_artifact_output"]["id"] = "agent_output/B.txt"
    policy.update(source_attribution_mode="required", high_stakes=True)
    return {
        "workspace": str(pipeline.workspace),
        "cards_is_b": pipeline.async_cards is case["cards_b"],
        "ledger_is_b": pipeline.run_ledger is case["ledger_b"],
        "artifact_id": artifacts["packet1_facts"]["primary_work_artifact_output"]["id"],
        "policy": dict(policy),
    }


def _held_inputs(case: dict[str, Any], artifacts: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pipeline = case["pipeline"]
    return {
        "workspace": str(pipeline.workspace),
        "cards_is_a": pipeline.async_cards is case["cards_a"],
        "ledger_is_a": pipeline.run_ledger is case["ledger_a"],
        "artifact_id": artifacts["packet1_facts"]["primary_work_artifact_output"]["id"],
        "policy": dict(policy),
    }


async def _run_materializer_case(case: dict[str, Any], *, mutate: bool, monkeypatch, record_property):
    pipeline, session_id = case["pipeline"], case["session_id"]
    summary_a = case["workspace_a"] / "runs" / session_id / "run_summary.json"
    summary_b = case["workspace_b"] / "runs" / session_id / "run_summary.json"
    events_a = case["workspace_a"] / "runs" / session_id / "events.log"
    events_b = case["workspace_b"] / "runs" / session_id / "events.log"
    artifacts = {
        "run_identity": {
            "run_id": session_id,
            "workload": "epic-closeout-input-capture",
            "start_time": _STARTED_AT,
            "identity_scope": "session_bootstrap",
            "projection_source": "session_bootstrap_artifacts",
            "projection_only": True,
        },
        "packet1_facts": {
            "primary_work_artifact_output": {"id": "agent_output/A.txt", "kind": "artifact"},
        },
    }
    policy = {"source_attribution_mode": "optional", "high_stakes": False}
    held: dict[str, Any] = {}
    target = case["workspace_a"] / "orket.log"
    hold = hold_sync(monkeypatch, Path, "exists", predicate=lambda path: Path(path) == target)
    task = asyncio.create_task(pipeline._materialize_run_summary(
        run_id=session_id,
        session_status="done",
        failure_reason=None,
        artifacts=artifacts,
        finalized_at=_FINALIZED_AT,
        phase_c_truth_policy=policy,
    ))

    def change_inputs() -> None:
        held.update(_mutate_case(case, artifacts, policy) if mutate else _held_inputs(case, artifacts, policy))

    original = (case["workspace_a"], case["cards_a"], case["ledger_a"])
    try:
        observation, results = await complete_held_operation(
            task=task,
            hold=hold,
            sqlite_path=case["sqlite_path"],
            record_property=record_property,
            paths=(
                summary_a,
                summary_b,
                events_a,
                events_b,
                Path(case["cards_a"].db_path),
                Path(case["cards_b"].db_path),
                case["receipt"],
            ),
            mutate=change_inputs,
        )
    finally:
        pipeline.workspace, pipeline.async_cards, pipeline.run_ledger = original
        hold.release.set()
    result = results[0]
    observation.update({
        "held_inputs": held,
        "result_type": type(result).__name__,
        "summary_a": await read_json(summary_a) if (await physical(summary_a))["is_file"] else None,
        "summary_b": await read_json(summary_b) if (await physical(summary_b))["is_file"] else None,
    })
    return observation, result


async def _final_observation(case: dict[str, Any], before: dict[str, Any], held: dict[str, Any]) -> dict[str, Any]:
    session_id = case["session_id"]
    summary_a = case["workspace_a"] / "runs" / session_id / "run_summary.json"
    summary_b = case["workspace_b"] / "runs" / session_id / "run_summary.json"
    after_a, after_b = await asyncio.gather(
        _repository_state(case["ledger_a"], case["cards_a"], session_id),
        _repository_state(case["ledger_b"], case["cards_b"], session_id),
    )
    physical_after = await asyncio.gather(*(
        physical(summary_a),
        physical(summary_b),
        physical(case["workspace_a"] / "runs" / session_id / "events.log"),
        physical(case["workspace_b"] / "runs" / session_id / "events.log"),
        physical(Path(case["cards_a"].db_path)),
        physical(Path(case["cards_b"].db_path)),
        physical(case["receipt"]),
    ))
    return {
        **held,
        "before": before,
        "after": {"a": after_a, "b": after_b},
        "physical_after": physical_after,
        "physical_after_names": [
            "summary_a", "summary_b", "events_a", "events_b", "cards_a", "cards_b", "receipt_a",
        ],
    }


def _assert_capture(observation: dict[str, Any], *, mutate: bool) -> None:
    summary = observation["summary_a"]
    audit = summary["truthful_runtime_packet2"]["narration_to_effect_audit"]
    attribution = summary["truthful_runtime_packet2"]["source_attribution"]
    packet2_events = [row for row in observation["after"]["a"]["events"] if row["kind"] == "packet2_fact"]
    assert observation["active_during_sqlite"] is True and observation["expired"] is False
    assert observation["worker_thread"] != observation["loop_thread"]
    assert observation["finished_after_release"] is True
    assert observation["result_type"] == "tuple" and isinstance(observation["materialized"], tuple)
    assert summary["truthful_runtime_packet1"]["provenance"]["primary_output_id"] == "agent_output/A.txt"
    assert attribution["mode"] == "optional" and attribution["high_stakes"] is False
    assert audit["verified_count"] == 1 and audit["entries"][0]["audit_status"] == "verified"
    assert len(packet2_events) == 1
    assert packet2_events[0]["packet2_facts"]["narration_to_effect_audit"]["verified_count"] == 1
    assert any("Set Status to 'done'" in row for row in observation["before"]["a"]["history"])
    assert not any("Set Status to 'done'" in row for row in observation["before"]["b"]["history"])
    assert observation["before"]["a"]["history"] == observation["after"]["a"]["history"]
    assert observation["before"]["b"] == observation["after"]["b"]
    assert observation["summary_b"] is None and observation["physical_after"][1]["exists"] is False
    assert observation["physical_after"][0]["is_file"] is True
    assert observation["physical_before"][3] == observation["physical_after"][3]
    assert observation["physical_before"][2]["sha256"] != observation["physical_after"][2]["sha256"]
    assert observation["materialized"][0] == summary
    assert observation["before"]["a"]["ledger_type"] == "AsyncProtocolRunLedgerRepository"
    assert observation["before"]["a"]["cards_type"] == "AsyncCardRepository"
    assert observation["held_inputs"]["artifact_id"] == ("agent_output/B.txt" if mutate else "agent_output/A.txt")
    assert observation["held_inputs"]["policy"]["source_attribution_mode"] == (
        "required" if mutate else "optional"
    )
    assert observation["held_inputs"]["cards_is_b" if mutate else "cards_is_a"] is True
    assert observation["held_inputs"]["ledger_is_b" if mutate else "ledger_is_a"] is True


@pytest.mark.parametrize("mutate", [False, True], ids=["unchanged", "mutated-after-admission"])
# Layer: integration
async def test_materialize_run_summary_captures_closeout_inputs(
    test_root, workspace, db_path, tmp_path, monkeypatch, record_property, mutate,
) -> None:
    session_id = f"closeout-input-capture-{'mutated' if mutate else 'unchanged'}"
    case = await _prepare_case(test_root, workspace, db_path, tmp_path, session_id)
    case.update(session_id=session_id, sqlite_path=tmp_path / "responsive.sqlite3")
    try:
        before = {
            "a": await _repository_state(case["ledger_a"], case["cards_a"], session_id),
            "b": await _repository_state(case["ledger_b"], case["cards_b"], session_id),
        }
        held, materialized = await _run_materializer_case(
            case, mutate=mutate, monkeypatch=monkeypatch, record_property=record_property)
        observation = await _final_observation(case, before, held)
        observation["materialized"] = materialized
        record_json(record_property, "epic_closeout_input_capture_observation", observation)
        _assert_capture(observation, mutate=mutate)
    finally:
        await close_pipeline(case["pipeline"])
