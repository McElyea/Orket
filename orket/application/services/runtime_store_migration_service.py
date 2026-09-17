"""Explicit offline cutover of one legacy control-plane authority, without dispatch."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_io
from orket.adapters.storage.epic_continuation_lock import EpicContinuationLocks
from orket.adapters.storage.runtime_store_migration_io import RuntimeStoreMigrationIO, hold_offline_stores
from orket.application.services.control_plane_snapshot_publication import snapshot_digest
from orket.application.services.runtime_store_binding_service import RuntimeStoreBindingService, legacy_session_bindings
from orket.core.contracts.epic_approval_recovery import EPIC_CONTINUATION_LOCK_ARTIFACT, EpicContinuationLockRef
from orket.core.contracts.epic_publication import EpicRunAdmission
from orket.core.contracts.runtime_store_binding import RuntimeStoreMigrationBinding


class RuntimeStoreMigrationService:
    def __init__(self, runtime_db: Path, *, legacy_control_plane_db: Path, legacy_invocation_root: Path):
        self.binding = RuntimeStoreBindingService(runtime_db.resolve())
        self.source = legacy_control_plane_db.resolve()
        self.invocation_root = legacy_invocation_root.resolve()
        self.io = RuntimeStoreMigrationIO()

    async def migrate(self, *, actor_ref: str, owners_stopped: bool) -> RuntimeStoreMigrationBinding:
        if owners_stopped is not True:
            raise ValueError("E_RUNTIME_STORE_MIGRATION_OFFLINE_REQUIRED")
        return await run_owned_io(
            lambda: self._migrate(actor_ref), label="runtime-store-migration", preserve_failure=True
        )

    async def _migrate(self, actor_ref: str) -> RuntimeStoreMigrationBinding:
        repository = self.binding.repository
        target = self.binding.control_plane_db
        staging = target.with_name(target.name + ".binding-staging.sqlite3")
        paths = (self.binding.runtime_db, repository.journal_db, self.source)
        async with hold_offline_stores(paths) as connections, AsyncExitStack() as locks:
            rows = await repository.admissions()
            legacy = legacy_session_bindings(rows)
            if not legacy:
                raise ValueError("E_RUNTIME_STORE_MIGRATION_NO_RELATIVE_HISTORY")
            retained = await repository.read_binding(self.binding.runtime_db)
            completed = await repository.read_binding(target)
            await self._validate_sources(
                rows, legacy, locks, allow_new_sessions=retained is not None and retained == completed
            )
            if completed is not None:
                if (
                    retained != completed
                    or completed.sessions != legacy
                    or completed.source_control_plane_db != str(self.source)
                    or completed.runtime_db != str(self.binding.runtime_db)
                    or completed.control_plane_db != str(target)
                    or completed.legacy_invocation_root != str(self.invocation_root)
                ):
                    raise ValueError("E_RUNTIME_STORE_BINDING_HISTORY_CONFLICT")
                if (
                    self.source != target
                    and await self.io.snapshot_digest(self.source) != completed.source_snapshot_digest
                ):
                    raise ValueError("E_RUNTIME_STORE_MIGRATION_SOURCE_CHANGED")
                await self.io.discard_published_staging(staging, target)
                return completed
            if self.source != target and await asyncio.to_thread(target.exists):
                raise ValueError("E_RUNTIME_STORE_MIGRATION_TARGET_CONFLICT")
            digest = await self.io.snapshot_digest(self.source)
            record = RuntimeStoreMigrationBinding(
                runtime_db=str(self.binding.runtime_db),
                control_plane_db=str(target),
                source_control_plane_db=str(self.source),
                legacy_invocation_root=str(self.invocation_root),
                source_snapshot_digest=digest,
                actor_ref=actor_ref,
                sessions=legacy,
            )
            if retained is not None and retained != record:
                raise ValueError("E_RUNTIME_STORE_BINDING_HISTORY_CONFLICT")
            if self.source != target:
                await self.io.backup(self.source, staging)
            runtime_connection = connections[self.binding.runtime_db]
            await repository.save_binding(self.binding.runtime_db, record, connection=runtime_connection)
            await runtime_connection.commit()
            await runtime_connection.execute("BEGIN IMMEDIATE")
            if self.source == target:
                await repository.save_binding(target, record, connection=connections[target])
                await connections[target].commit()
            else:
                await repository.save_binding(staging, record)
                await self.io.publish(staging, target)
            if await repository.read_binding(target) != record:
                raise ValueError("E_RUNTIME_STORE_BINDING_UNCONFIRMED")
            return record

    async def _validate_sources(self, rows, legacy, locks, *, allow_new_sessions):
        by_session = {item.session_id: item for item in legacy}
        for session_id, payload, _ in rows:
            if session_id not in by_session:
                if not allow_new_sessions:
                    raise ValueError("E_RUNTIME_STORE_MIGRATION_MIXED_AUTHORITY")
                continue
            admission = EpicRunAdmission.model_validate_json(payload)
            relative = Path(by_session[session_id].original_runtime_db)
            resolved = await asyncio.to_thread((self.invocation_root / relative).resolve)
            old_control = (
                Path(admission.request["scope"]["workspace"]) / relative.parent / "control_plane_records.sqlite3"
            )
            if resolved != self.binding.runtime_db or await asyncio.to_thread(old_control.resolve) != self.source:
                raise ValueError("E_RUNTIME_STORE_MIGRATION_SOURCE_BINDING_CONFLICT")
            pause = await self.binding.repository.approval_pause(session_id)
            if admission.phase == "active" and pause is None:
                raise ValueError("E_RUNTIME_STORE_MIGRATION_ACTIVE_OWNER_UNRESOLVED")
            if pause is not None and pause.request != admission.request:
                raise ValueError("E_RUNTIME_STORE_MIGRATION_PAUSE_REQUEST_CONFLICT")
            marker = pause.artifacts.get(EPIC_CONTINUATION_LOCK_ARTIFACT) if pause is not None else None
            expected = EpicContinuationLockRef.model_validate(marker) if marker is not None else None
            await locks.enter_async_context(
                EpicContinuationLocks(self.binding.repository.journal_db).hold(session_id, expected=expected)
            )
        await self._validate_control_plane({row[0] for row in rows})

    async def _validate_control_plane(self, sessions: set[str]) -> None:
        records = await self.binding.repository.run_configurations(self.source)
        targets = await self.binding.repository.approval_targets(sessions)
        if not targets.issubset({run.run_id for run, _ in records}):
            raise ValueError("E_RUNTIME_STORE_MIGRATION_APPROVAL_TARGET_MISSING")
        for run, configuration in records:
            if (
                configuration.snapshot_id != run.configuration_snapshot_id
                or configuration.snapshot_digest != run.configuration_digest
                or snapshot_digest(configuration.configuration_payload) != run.configuration_digest
            ):
                raise ValueError("E_RUNTIME_STORE_MIGRATION_RUN_HISTORY_CONFLICT")
            if configuration.configuration_payload.get("session_id") not in sessions:
                raise ValueError("E_RUNTIME_STORE_MIGRATION_MIXED_AUTHORITY")
