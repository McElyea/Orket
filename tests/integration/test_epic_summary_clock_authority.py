"""Explicit clock inputs bind identity/summary; clock refusal preserves the run result."""
from __future__ import annotations

import asyncio
import json
from datetime import timedelta

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.application.test_execution_pipeline_run_ledger import (
    _write_epic_assets,
    _write_protocol_receipt,
    _write_protocol_write_receipts,
)
from tests.helpers.card_completion import complete_existing_card
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class OutcomeClock(ProtocolLedgerClock):
    def __init__(self):
        super().__init__()
        self.reverse_next = False
        self.observations = []

    def utc_now(self):
        observed = super().utc_now()
        if self.reverse_next:
            observed -= timedelta(hours=1)
            self.reverse_next = False
        self.observations.append(observed.isoformat())
        return observed


async def execute_without_source_attribution(pipeline, workspace, run_id):
    await asyncio.to_thread(_write_protocol_write_receipts, workspace, session_id=run_id,
        rows=[("ISSUE-1", "lead_architect", 1, "agent_output/main.py", "op-main")])
    await asyncio.to_thread(_write_protocol_receipt, workspace, session_id=run_id,
        issue_id="ISSUE-1", role_name="lead_architect", turn_index=1, tool="update_issue_status",
        tool_args={"issue_id": "ISSUE-1", "status": "done"},
        execution_result={"ok": True, "issue_id": "ISSUE-1", "status": "done"},
        operation_id="op-status-done", materialize_artifact=False)
    await complete_existing_card(pipeline.async_cards, "ISSUE-1", workspace, service=pipeline.runtime_context.card_completion)


@pytest.mark.parametrize("reverse", [False, True], ids=["ordered", "negative-summary-duration"])
# Layer: integration
async def test_source_attribution_failure_preserves_explicit_clock_truth(test_root, workspace, db_path, monkeypatch, reverse):
    await asyncio.to_thread(_write_epic_assets, test_root, "clock_source_attribution",
                            truthful_runtime={"source_attribution_mode": "required"})
    clock = OutcomeClock()
    # Keep ledger event time independently valid while reversing one outcome observation.
    ledger_time = clock.current.isoformat()
    ledger = AsyncProtocolRunLedgerRepository(workspace, timestamp_factory=lambda: ledger_time)
    pipeline = ExecutionPipeline(workspace=workspace, department="core", db_path=db_path,
        config_root=test_root, run_ledger_repo=ledger, runtime_inputs=clock)

    async def work(**kwargs):
        await execute_without_source_attribution(pipeline, workspace, str(kwargs["run_id"]))
        clock.reverse_next = reverse

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", work)
    try:
        result = await pipeline.run_card("clock_source_attribution", build_id="clock-build", session_id="clock-source")
        run = await ledger.get_run("clock-source")
        events = await ledger.list_events("clock-source")
        identity = run["artifact_json"]["run_identity"]
        assert identity["start_time"] in clock.observations
        assert not result.succeeded and run["status"] == "terminal_failure"
        assert run["failure_reason"] == "source_attribution_receipt_missing"
        summary = run["summary_json"]
        emitted = json.loads(await asyncio.to_thread((workspace / "runs/clock-source/run_summary.json").read_text, encoding="utf-8"))
        assert emitted == summary
        errors = [event for event in events if event["kind"] == "packet1_emission_failure"]
        if reverse:
            assert summary["is_degraded"] and summary["duration_ms"] is None
            assert [event["error"] for event in errors] == ["run_summary_duration_negative"]
        else:
            assert not summary["is_degraded"] and summary["duration_ms"] >= 0 and not errors
            packet = summary["truthful_runtime_packet2"]["source_attribution"]
            assert packet["synthesis_status"] == "blocked"
            assert packet["missing_requirements"] == ["source_attribution_receipt_missing"]
    finally:
        await pipeline.close()
