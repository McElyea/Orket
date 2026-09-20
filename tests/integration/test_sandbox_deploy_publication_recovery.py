"""Integration: real SQLite publication with controlled Docker observations and clocks."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import closing

import pytest

from orket.core.domain.sandbox import TechStack
from tests.integration.test_sandbox_orchestrator_lifecycle import FakeLifecycleRunner, _orchestrator

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _owner(tmp_path):
    runner = FakeLifecycleRunner(compose_project="orket-sandbox-rock-1", sandbox_id="sandbox-rock-1", run_id="rock-1")
    owner = _orchestrator(tmp_path, runner)
    owner._initial_health_attempts = 2
    owner._initial_health_delay_seconds = 0
    owner._now = lambda: "2030-01-01T00:00:21+00:00"
    owner.lifecycle_service._now = lambda: "2030-01-01T00:00:20+00:00"
    return owner


async def _create(owner, tmp_path):
    return await owner.create_sandbox(rock_id="rock-1", project_name="Publication recovery",
                                      tech_stack=TechStack.FASTAPI_REACT_POSTGRES, workspace_path=str(tmp_path))


def _journal_rows(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        rows = connection.execute("SELECT payload_json FROM effect_journal_entries WHERE run_id=?", ("rock-1",)).fetchall()
        return [(json.loads(payload)["effect_id"],) for (payload,) in rows]


def _execute_sql(path, statement):
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(statement)


async def test_clock_regression_retry_verifies_deployment_journal(tmp_path):
    owner = _owner(tmp_path)
    original = owner.lifecycle_service.mark_deployment_verified
    failures = []

    async def regressed(**kwargs):
        owner.lifecycle_service._now = lambda: "2030-01-01T00:00:01+00:00"
        try:
            return await original(**kwargs)
        except ValueError as exc:
            failures.append(str(exc))
            raise
        finally:
            owner.lifecycle_service._now = lambda: "2030-01-01T00:00:21+00:00"

    owner.lifecycle_service.mark_deployment_verified = regressed
    result = await _create(owner, tmp_path)
    assert failures == ["lease publication timestamps must increase monotonically"]
    assert result.status.value == "running" and result.health_checks_failed == 1
    expected = [("sandbox-effect:sandbox-rock-1:deploy:lease_epoch:00000001",)]
    database = tmp_path / "control_plane_records.sqlite3"
    assert await asyncio.to_thread(_journal_rows, database) == expected
    assert await owner.health_check("sandbox-rock-1")
    assert await asyncio.to_thread(_journal_rows, database) == expected


async def test_native_journal_write_refusal_cannot_become_healthy_on_retry(tmp_path):
    owner = _owner(tmp_path)
    database = tmp_path / "control_plane_records.sqlite3"
    original = owner.lifecycle_service.mark_deployment_verified

    async def refuse(**kwargs):
        await asyncio.to_thread(_execute_sql, database,
            "CREATE TRIGGER refuse_deploy BEFORE INSERT ON effect_journal_entries "
            "BEGIN SELECT RAISE(ABORT, 'controlled deployment journal refusal'); END;")
        return await original(**kwargs)

    owner.lifecycle_service.mark_deployment_verified = refuse
    with pytest.raises(sqlite3.IntegrityError, match="controlled deployment journal refusal"):
        await _create(owner, tmp_path)
    owner.lifecycle_service._now = lambda: "2030-01-01T00:00:21+00:00"
    with pytest.raises(sqlite3.IntegrityError, match="controlled deployment journal refusal"):
        await owner.health_check("sandbox-rock-1")
    assert await asyncio.to_thread(_journal_rows, database) == []
    await asyncio.to_thread(_execute_sql, database, "DROP TRIGGER refuse_deploy;")
    assert await owner.health_check("sandbox-rock-1")
    expected = [("sandbox-effect:sandbox-rock-1:deploy:lease_epoch:00000001",)]
    assert await asyncio.to_thread(_journal_rows, database) == expected
    assert await owner.health_check("sandbox-rock-1")
    assert await asyncio.to_thread(_journal_rows, database) == expected
