"""Database smoke owners prepare logging before real repository initialization."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

from orket.adapters.observability.logging_context import selected_logging
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging, settle_log_write_frontier
from scripts.ci.migration_smoke_validator import _bootstrap, _validate
from scripts.governance.release_smoke import _bootstrap_databases

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[2]


def _assert_schema(runtime_db, webhook_db):
    with sqlite3.connect(runtime_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM issues").fetchone() == (0,)
    with sqlite3.connect(webhook_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM pr_review_cycles").fetchone() == (0,)


@pytest.mark.parametrize("caller", ["migration", "release"])
@pytest.mark.parametrize("outer_binding", [False, True], ids=["unbound", "other-caller"])
async def test_database_bootstrap_prepares_logging(tmp_path, monkeypatch, caller, outer_binding):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_TIMEZONE", "UTC")
    runtime_db, webhook_db = tmp_path / "runtime.db", tmp_path / "webhook.db"
    outer = await prepare_logging(LoggingInputs(tmp_path / "other", timezone_name="America/Phoenix"))
    with bind_logging(outer) if outer_binding else nullcontext():
        before = selected_logging(required=False)
        if caller == "migration":
            await _bootstrap(runtime_db, webhook_db)
        else:
            await _bootstrap_databases(str(runtime_db), str(webhook_db))
        assert selected_logging(required=False) is before
    await asyncio.to_thread(_assert_schema, runtime_db, webhook_db)
    await asyncio.to_thread(settle_log_write_frontier)
    rows = [json.loads(line) for line in (await asyncio.to_thread(
        (tmp_path / "workspace/default/orket.log").read_text, encoding="utf-8")).splitlines()]
    events = [row for row in rows if row["event"] == "webhook_db"]
    assert len(events) == 1 and events[0]["timestamp"].endswith("+00:00")
    assert not await asyncio.to_thread((tmp_path / "other/workspace").exists)


async def test_migration_smoke_native_bootstrap_migrate_validate(tmp_path, record_property):
    environment = {**os.environ, "PYTHONPATH": str(ROOT), "ORKET_DISABLE_SANDBOX": "1",
                   "ORKET_TIMEZONE": "UTC"}
    runtime_db, webhook_db = tmp_path / "runtime.db", tmp_path / "webhook.db"
    db_args = ["--runtime-db", str(runtime_db), "--webhook-db", str(webhook_db)]
    supervisor = CommandProcessSupervisor(tmp_path, cancellation_event="bootstrap_test_cancelled")
    commands = [
        ["scripts.ci.migration_smoke_validator", *db_args, "--bootstrap"],
        ["scripts.governance.run_migrations", *db_args, "--migration-dir", str(ROOT / "scripts/migrations")],
        ["scripts.ci.migration_smoke_validator", *db_args, "--validate"],
    ]
    receipts = []
    for arguments in commands:
        result = await supervisor.run([sys.executable, "-m", *arguments], cwd=tmp_path,
                                      timeout_seconds=30, environment=environment)
        assert result.cleanup_confirmed and result.capture_complete
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        receipts.append(result.lifetime())
    assert b"Migration smoke validation passed" in result.stdout
    await asyncio.to_thread(_assert_schema, runtime_db, webhook_db)
    await asyncio.to_thread(_validate, runtime_db, webhook_db)
    record_property("native_migration_lifetimes", json.dumps(receipts))
