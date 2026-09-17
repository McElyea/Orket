"""Admit one physical store pair and preserve explicitly migrated request identity."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.adapters.storage.runtime_store_binding_repository import RuntimeStoreBindingRepository
from orket.core.contracts.epic_publication import EpicRunAdmission
from orket.core.contracts.runtime_store_binding import LegacyRuntimeSessionBinding
from orket.core.domain.outward_authorization import args_hash
from orket.runtime_paths import control_plane_db_for_runtime


def legacy_session_bindings(rows: list[tuple[str, str, str]]) -> tuple[LegacyRuntimeSessionBinding, ...]:
    sessions = []
    for session_id, payload, digest in rows:
        admission = EpicRunAdmission.model_validate_json(payload)
        if admission.session_id != session_id or admission.digest() != digest:
            raise ValueError("E_RUNTIME_STORE_ADMISSION_INTEGRITY")
        reference = admission.request.get("scope", {}).get("runtime_db")
        if not isinstance(reference, str) or not reference:
            raise ValueError("E_RUNTIME_STORE_ADMISSION_SCOPE_MISSING")
        if not Path(reference).is_absolute():
            sessions.append(
                LegacyRuntimeSessionBinding(
                    session_id=session_id, original_runtime_db=reference, request_digest=args_hash(admission.request)
                )
            )
    return tuple(sorted(sessions, key=lambda item: item.session_id))


class RuntimeStoreBindingService:
    def __init__(self, runtime_db: str | Path):
        self.runtime_db = Path(runtime_db)
        self.control_plane_db = control_plane_db_for_runtime(runtime_db=self.runtime_db)
        self.repository = RuntimeStoreBindingRepository(self.runtime_db, self.control_plane_db)
        self._sessions: tuple[LegacyRuntimeSessionBinding, ...] = ()
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        await run_owned_io(self._initialize, label="runtime-store-binding", preserve_failure=True)

    async def _initialize(self) -> None:
        async with self._lock:
            if self._initialized:
                return
            legacy = legacy_session_bindings(await self.repository.admissions())
            runtime = await self.repository.read_binding(self.runtime_db)
            control = await self.repository.read_binding(self.control_plane_db)
            if runtime != control:
                raise ValueError("E_RUNTIME_STORE_BINDING_INCOMPLETE")
            if runtime is None:
                if legacy:
                    raise ValueError("E_RUNTIME_STORE_MIGRATION_REQUIRED")
            elif (
                runtime.runtime_db != str(self.runtime_db)
                or runtime.control_plane_db != str(self.control_plane_db)
                or runtime.sessions != legacy
            ):
                raise ValueError("E_RUNTIME_STORE_BINDING_HISTORY_CONFLICT")
            self._sessions, self._initialized = legacy, True

    def request_scope(self, session_id: str, scope: dict[str, Any]) -> dict[str, Any]:
        if not self._initialized:
            raise ValueError("E_RUNTIME_STORE_BINDING_NOT_INITIALIZED")
        if scope.get("runtime_db") != str(self.runtime_db):
            raise ValueError("E_RUNTIME_STORE_SCOPE_CONFLICT")
        result = dict(scope)
        prior = next((item for item in self._sessions if item.session_id == session_id), None)
        if prior is not None:
            result["runtime_db"] = prior.original_runtime_db
        return result
