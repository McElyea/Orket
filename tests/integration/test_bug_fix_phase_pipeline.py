"""Real pipeline composition, bug-fix SQLite effects and workspace logging."""
import asyncio
import json

import pytest

from orket.adapters.vcs.webhook_db import WebhookDatabase
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_pipeline_bug_fix_phase_uses_supplied_time_and_workspace(test_root, workspace, db_path):
    clock = ProtocolLedgerClock()
    clock.current = clock.current.replace(year=2041)
    expected = clock.current.isoformat()
    async with ExecutionPipeline.open(workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock) as pipeline:
        # Isolate this real persistence adapter; the pipeline's default webhook location is a separate authority.
        pipeline.bug_fix_manager.db = WebhookDatabase(db_path=test_root / "bug-fix.sqlite3")
        try:
            phase = await pipeline.bug_fix_manager.start_phase("collection")
            saved = await WebhookDatabase(db_path=test_root / "bug-fix.sqlite3").get_bug_fix_phase("collection")
            assert phase.started_at == saved.started_at == expected
            logs = await asyncio.to_thread((workspace / "orket.log").read_text, encoding="utf-8")
            events = [json.loads(line) for line in logs.splitlines()]
            assert any(row["event"] == "bug_fix_phase_started" for row in events)
        finally:
            await pipeline.close()
