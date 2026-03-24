# Layer: integration

from __future__ import annotations

import aiosqlite
import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import (
    AsyncSandboxLifecycleRepository,
    SandboxOperationIntegrityError,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxLifecycleError, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import (
    ManagedResourceInventory,
    SandboxApprovalRecord,
    SandboxLifecycleEventRecord,
    SandboxLifecycleRecord,
    SandboxLifecycleSnapshotRecord,
    SandboxOperationDedupeEntry,
)


def _record(**overrides) -> SandboxLifecycleRecord:
    payload = {
        "sandbox_id": "sb-1",
        "compose_project": "orket-sandbox-sb-1",
        "workspace_path": "workspace/sb-1",
        "run_id": "run-1",
        "owner_instance_id": "runner-a",
        "lease_epoch": 2,
        "lease_expires_at": "2026-03-11T00:05:00+00:00",
        "state": SandboxState.ACTIVE,
        "cleanup_state": CleanupState.NONE,
        "record_version": 3,
        "created_at": "2026-03-11T00:00:00+00:00",
        "last_heartbeat_at": "2026-03-11T00:01:00+00:00",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(
            containers=["sb-1-api"],
            networks=["sb-1-net"],
            managed_volumes=["sb-1-db"],
        ),
        "requires_reconciliation": False,
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


@pytest.mark.asyncio
async def test_repository_round_trips_lifecycle_record(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    record = _record()

    await repo.save_record(record)
    loaded = await repo.get_record("sb-1")

    assert loaded is not None
    assert loaded.sandbox_id == "sb-1"
    assert loaded.record_version == 3
    assert loaded.managed_resource_inventory.managed_volumes == ["sb-1-db"]


@pytest.mark.asyncio
async def test_repository_round_trips_lifecycle_snapshot(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    record = _record()
    snapshot = SandboxLifecycleSnapshotRecord(
        snapshot_id="sandbox-lifecycle-snapshot:sb-1:00000003",
        sandbox_id="sb-1",
        record_version=3,
        created_at="2026-03-11T00:10:00+00:00",
        integrity_digest="sha256:test",
        record=record,
    )

    stored = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot.snapshot_id)
    listed = await repo.list_snapshots("sb-1")

    assert stored.snapshot_id == snapshot.snapshot_id
    assert loaded is not None
    assert loaded.record.record_version == 3
    assert listed == [snapshot]


@pytest.mark.asyncio
async def test_repository_rejects_unsupported_future_schema_record_on_read(tmp_path) -> None:
    db_path = tmp_path / "sandbox_lifecycle.db"
    repo = AsyncSandboxLifecycleRepository(db_path)
    await repo.save_record(_record())

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "UPDATE sandbox_lifecycle_records SET schema_version = ? WHERE sandbox_id = ?",
            ("99.0", "sb-1"),
        )
        await conn.commit()

    with pytest.raises(SandboxLifecycleError, match="schema_version"):
        await repo.get_record("sb-1")


@pytest.mark.asyncio
async def test_repository_rejects_unsupported_policy_record_on_read(tmp_path) -> None:
    db_path = tmp_path / "sandbox_lifecycle.db"
    repo = AsyncSandboxLifecycleRepository(db_path)
    await repo.save_record(_record())

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "UPDATE sandbox_lifecycle_records SET policy_version = ? WHERE sandbox_id = ?",
            ("docker_sandbox_lifecycle.v99", "sb-1"),
        )
        await conn.commit()

    with pytest.raises(SandboxLifecycleError, match="policy_version"):
        await repo.get_record("sb-1")


@pytest.mark.asyncio
async def test_repository_reuses_operation_result_for_same_payload_hash(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    first = SandboxOperationDedupeEntry(
        operation_id="op-1",
        payload_hash="hash-a",
        result_payload={"ok": True},
        created_at="2026-03-11T00:00:00+00:00",
    )

    stored = await repo.remember_operation(first)
    reused = await repo.remember_operation(
        SandboxOperationDedupeEntry(
            operation_id="op-1",
            payload_hash="hash-a",
            result_payload={"ok": False},
            created_at="2026-03-11T00:01:00+00:00",
        )
    )

    assert stored.result_payload == {"ok": True}
    assert reused.result_payload == {"ok": True}


@pytest.mark.asyncio
async def test_repository_rejects_operation_id_payload_hash_mismatch(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.remember_operation(
        SandboxOperationDedupeEntry(
            operation_id="op-1",
            payload_hash="hash-a",
            result_payload={"ok": True},
            created_at="2026-03-11T00:00:00+00:00",
        )
    )

    with pytest.raises(SandboxOperationIntegrityError, match="different payload hash"):
        await repo.remember_operation(
            SandboxOperationDedupeEntry(
                operation_id="op-1",
                payload_hash="hash-b",
                result_payload={"ok": True},
                created_at="2026-03-11T00:01:00+00:00",
            )
        )


@pytest.mark.asyncio
async def test_repository_persists_approvals_and_events(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_approval(
        SandboxApprovalRecord(
            approval_id="approval-1",
            sandbox_id="sb-1",
            action="cleanup",
            approved_by="operator-a",
            reason="verified orphan",
            created_at="2026-03-11T00:00:00+00:00",
        )
    )
    await repo.append_event(
        SandboxLifecycleEventRecord(
            event_id="evt-1",
            sandbox_id="sb-1",
            event_kind="lifecycle",
            event_type="sandbox.cleanup_scheduled",
            created_at="2026-03-11T00:02:00+00:00",
            payload={"reason_code": TerminalReason.LEASE_EXPIRED.value},
        )
    )

    approvals = await repo.list_approvals("sb-1")
    events = await repo.list_events("sb-1")

    assert len(approvals) == 1
    assert approvals[0].approved_by == "operator-a"
    assert len(events) == 1
    assert events[0].payload["reason_code"] == TerminalReason.LEASE_EXPIRED.value


@pytest.mark.asyncio
async def test_repository_revokes_approval_in_place(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_approval(
        SandboxApprovalRecord(
            approval_id="approval-1",
            sandbox_id="sb-1",
            action="cleanup",
            approved_by="operator-a",
            created_at="2026-03-11T00:00:00+00:00",
        )
    )

    updated = await repo.revoke_approval(
        "approval-1",
        revoked_by="operator-b",
        revoked_at="2026-03-11T00:05:00+00:00",
    )
    approvals = await repo.list_approvals("sb-1")

    assert updated is True
    assert approvals[0].revoked_by == "operator-b"
    assert approvals[0].revoked_at == "2026-03-11T00:05:00+00:00"
