"""Persistence validation, immutable admissions and caller mutation boundaries."""
import asyncio
import json

import aiosqlite
import pytest
from pydantic import ValidationError

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
    ControlPlaneExecutionConflictError,
)
from orket.core.domain import AttemptState
from tests.integration.test_control_plane_state_revision import KINDS, changed, initial, read, save

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
TABLES = {"run": "control_plane_runs", "attempt": "control_plane_attempts", "step": "control_plane_steps"}


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("revision", [False, True])
# Layer: integration
async def test_boolean_revision_cannot_impersonate_observed_integer(tmp_path, kind, revision):
    repository = AsyncControlPlaneExecutionRepository(tmp_path / "control.sqlite3")
    current = await save(repository, kind, initial(kind))
    if revision:
        current = await save(repository, kind, changed(current, kind))
    with pytest.raises(ValidationError):
        await save(repository, kind, current.model_copy(update={"state_revision": revision}))
    assert await read(repository, kind) == current


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("revision", [True, "0", 0.0, -1])
# Layer: integration
async def test_invalid_incoming_revision_does_not_create_or_mutate_rows(tmp_path, kind, revision):
    repository = AsyncControlPlaneExecutionRepository(tmp_path / "control.sqlite3")
    invalid = initial(kind).model_copy(update={"state_revision": revision})
    with pytest.raises(ValidationError):
        await save(repository, kind, invalid)
    assert await read(repository, kind) is None
    current = await save(repository, kind, initial(kind))
    with pytest.raises(ValidationError):
        await save(repository, kind, invalid)
    assert await read(repository, kind) == current


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("revision", [None, True, "0", 0.0, -1])
# Layer: integration
async def test_malformed_persisted_revision_is_refused_without_backfill(tmp_path, kind, revision):
    path = tmp_path / "control.sqlite3"
    repository = AsyncControlPlaneExecutionRepository(path)
    current = await save(repository, kind, initial(kind))
    payload = current.model_dump(mode="json")
    payload["state_revision"] = revision
    raw = json.dumps(payload)
    async with aiosqlite.connect(path) as connection:
        await connection.execute(f"UPDATE {TABLES[kind]} SET payload_json=?", (raw,))
        await connection.commit()
    with pytest.raises(ValueError):
        await read(repository, kind)
    with pytest.raises(ValueError):
        await save(repository, kind, current)
    async with aiosqlite.connect(path) as connection:
        cursor = await connection.execute(f"SELECT payload_json FROM {TABLES[kind]}")
        assert (await cursor.fetchone())[0] == raw


@pytest.mark.parametrize("kind,field,value", [
    ("attempt", "run_id", "different-run"), ("attempt", "starting_state_snapshot_ref", "different-snapshot"),
    ("attempt", "attempt_ordinal", 2), ("step", "attempt_id", "different-attempt"),
    ("step", "input_ref", "different-input"), ("step", "step_kind", "different-kind"),
])
# Layer: integration
async def test_current_revision_does_not_authorize_rebinding_admission(tmp_path, kind, field, value):
    repository = AsyncControlPlaneExecutionRepository(tmp_path / "control.sqlite3")
    current = await save(repository, kind, initial(kind))
    with pytest.raises(ControlPlaneExecutionConflictError, match="AUTHORITY_CONFLICT"):
        await save(repository, kind, current.model_copy(update={field: value}))
    assert await read(repository, kind) == current


# Layer: integration
async def test_attempt_execution_start_can_change_only_on_initial_activation(tmp_path):
    repository = AsyncControlPlaneExecutionRepository(tmp_path / "control.sqlite3")
    created = initial("attempt").model_copy(update={"attempt_state": AttemptState.CREATED})
    created = await save(repository, "attempt", created)
    executed = await save(repository, "attempt", created.model_copy(update={
        "attempt_state": AttemptState.EXECUTING, "start_timestamp": "2026-09-14T00:00:30+00:00"}))
    assert executed.state_revision == 1 and executed.start_timestamp != created.start_timestamp
    with pytest.raises(ControlPlaneExecutionConflictError, match="AUTHORITY_CONFLICT"):
        await save(repository, "attempt", executed.model_copy(update={"start_timestamp": created.start_timestamp}))
    assert await read(repository, "attempt") == executed


@pytest.mark.parametrize("kind", KINDS)
# Layer: integration
async def test_caller_mutation_during_await_cannot_change_submitted_write(tmp_path, monkeypatch, kind):
    repository = AsyncControlPlaneExecutionRepository(tmp_path / "control.sqlite3")
    entered, release = asyncio.Event(), asyncio.Event()
    original_execute = repository._execute

    async def suspended_execute(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original_execute(*args, **kwargs)

    monkeypatch.setattr(repository, "_execute", suspended_execute)
    proposed = initial(kind)
    expected = proposed.model_dump(mode="json") | {"state_revision": 0}
    task = asyncio.create_task(save(repository, kind, proposed))
    try:
        await asyncio.wait_for(entered.wait(), 10)
        proposed.state_revision = 57
        if kind == "run":
            proposed.namespace_scope = "changed-during-await"
        elif kind == "attempt":
            proposed.starting_state_snapshot_ref = "changed-during-await"
        else:
            proposed.receipt_refs.append("changed-during-await")
    finally:
        release.set()
        saved = await asyncio.wait_for(task, 10)
    assert saved.model_dump(mode="json") == expected
    assert await read(repository, kind) == saved
