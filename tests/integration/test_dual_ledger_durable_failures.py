"""Durable faults, conflicting owners and recovery use actual local backends."""
import asyncio
import json

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.application.services.dual_write_run_ledger import AsyncDualModeLedgerRepository
from orket.core.contracts.local_file_lock import LocalFileLockError
from tests.helpers.dual_ledger import HeldSQLite, repositories, start_values
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_shared_protocol_root_refuses_competing_database_owner(tmp_path):
    """Layer: integration. Ownership covers both backends even when journals differ."""
    owner = repositories(tmp_path, database="a.db", sqlite_type=HeldSQLite)
    contender = repositories(tmp_path, database="b.db")
    task = asyncio.create_task(owner.start_run(**start_values()))
    await asyncio.wait_for(owner.sqlite_repo.entered.wait(), 2)
    try:
        with pytest.raises(LocalFileLockError, match="owner_busy"):
            await contender.start_run(**start_values("conflict"))
    finally:
        owner.sqlite_repo.release.set()
        await task
    assert await contender.sqlite_repo.get_run("run") is None
    with pytest.raises(RuntimeError, match="CONTENT_CONFLICT"):
        await contender.start_run(**start_values("conflict"))


async def test_recovery_after_clear_failure_verifies_effect_without_repeating_it(tmp_path, monkeypatch):
    """Layer: integration. Failed journal clearing leaves verified effects recoverable."""
    repo = repositories(tmp_path)
    actual_write = repo._store.write

    async def fail_clear(rows):
        if not rows:
            raise OSError("injected durable clear failure")
        await actual_write(rows)

    monkeypatch.setattr(repo._store, "write", fail_clear)
    with pytest.raises(OSError, match="durable clear"):
        await repo.start_run(**start_values())
    assert json.loads(repo._intent_path.read_bytes())["pending"]
    recovered = repositories(tmp_path)
    await recovered.initialize()
    assert await recovered._load_intents() == []
    assert [row["kind"] for row in await recovered.list_events("run")] == ["run_started"]
    assert (await recovered.sqlite_repo.get_run("run"))["run_name"] == "original"


class NoEffectProtocol(AsyncProtocolRunLedgerRepository):
    async def start_run(self, **kwargs):
        return {"kind": "run_started"}


async def test_success_shaped_return_without_effect_retains_intent_and_refuses_success(tmp_path):
    """Layer: integration. Readback detects a controlled adapter's missing physical effect."""
    repo = AsyncDualModeLedgerRepository(sqlite_repo=AsyncRunLedgerRepository(tmp_path / "runtime.db"),
                                         protocol_repo=NoEffectProtocol(tmp_path / "protocol"))
    with pytest.raises(RuntimeError, match="EFFECT_UNVERIFIED:protocol"):
        await repo.start_run(**start_values())
    assert (await repo.sqlite_repo.get_run("run"))["run_name"] == "original"
    assert await repo.protocol_repo.get_run("run") is None
    assert json.loads(repo._intent_path.read_bytes())["pending"]


@pytest.mark.parametrize("raw", ["", '{"schema_version":"1.0","pending":[{}]}'])
async def test_unbound_legacy_journal_is_preserved_and_blocks_replay(tmp_path, raw):
    """Layer: integration. Legacy data cannot select a new backend binding implicitly."""
    path = tmp_path / ".orket" / "dual_write_intents.json"
    path.parent.mkdir()
    path.write_text(raw, encoding="utf-8")
    repo = repositories(tmp_path)
    with pytest.raises(RuntimeError, match="LEGACY_UNBOUND"):
        await repo.start_run(**start_values())
    assert path.read_text(encoding="utf-8") == raw
    assert not (tmp_path / "runtime.db").exists()


async def test_finalized_timestamp_and_payload_are_verified(tmp_path):
    """Layer: integration. A finalization retains the supplied timestamp on both backends."""
    repo = repositories(tmp_path)
    await repo.start_run(**start_values())
    timestamp = "2030-01-01T00:00:00+00:00"
    await repo.finalize_run(session_id="run", status="incomplete", summary={"closed": True}, finalized_at=timestamp)
    assert (await repo.sqlite_repo.get_run("run"))["ended_at"] == timestamp
    finals = [row for row in await repo.protocol_repo.list_events("run") if row["kind"] == "run_finalized"]
    assert len(finals) == 1 and finals[0]["timestamp"] == timestamp
    with pytest.raises(RuntimeError, match="CONTENT_CONFLICT"):
        await repo.finalize_run(session_id="run", status="incomplete", summary={"closed": False}, finalized_at=timestamp)
    assert (await repo.sqlite_repo.get_run("run"))["summary_json"]["closed"] is True


async def test_protocol_primary_failure_is_not_reported_as_completed_lifecycle(tmp_path):
    """Layer: integration. A failed authoritative backend cannot borrow mirror success."""
    class UnavailableProtocol(AsyncProtocolRunLedgerRepository):
        async def start_run(self, **kwargs):
            raise OSError("provider storage unavailable")

    repo = AsyncDualModeLedgerRepository(sqlite_repo=AsyncRunLedgerRepository(tmp_path / "runtime.db"),
        protocol_repo=UnavailableProtocol(tmp_path / "protocol", timestamp_factory=ProtocolLedgerClock().utc_now_iso),
        primary_mode="protocol")
    with pytest.raises(RuntimeError, match="PRIMARY_UNAVAILABLE"):
        await repo.start_run(**start_values())
    assert json.loads(repo._intent_path.read_bytes())["pending"]


async def test_relative_backend_paths_refuse_ambient_working_directory_binding(tmp_path):
    """Layer: integration. Admission requires explicit absolute storage identities."""
    with pytest.raises(RuntimeError, match="absolute_backend_paths"):
        AsyncDualModeLedgerRepository(sqlite_repo=AsyncRunLedgerRepository("runtime.db"),
                                       protocol_repo=AsyncProtocolRunLedgerRepository(tmp_path / "protocol"))


@pytest.mark.parametrize("target", ["sqlite", "protocol"])
async def test_backend_binding_drift_is_refused_before_next_operation(tmp_path, target):
    """Layer: integration. Mutating an adapter target cannot bypass journal binding."""
    repo = repositories(tmp_path)
    await repo.start_run(**start_values())
    if target == "sqlite":
        repo.sqlite_repo.db_path = str(tmp_path / "other.db")
    else:
        repo.protocol_repo.root = tmp_path / "other-protocol"
    with pytest.raises(RuntimeError, match="BINDING_DRIFT"):
        await repo.get_run("run")
    assert not (tmp_path / "other.db").exists()
    assert not (tmp_path / "other-protocol").exists()
