from __future__ import annotations

from pathlib import Path

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.runtime_paths import resolve_control_plane_db_path

from .turn_tool_control_plane_service import TurnToolControlPlaneService


def build_turn_tool_control_plane_service(
    db_path: str | Path | None = None,
) -> TurnToolControlPlaneService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return TurnToolControlPlaneService(
        execution_repository=AsyncControlPlaneExecutionRepository(resolved_db_path),
        publication=publication,
        transactions=SQLiteControlPlaneTransactions(resolved_db_path),
        execution_owners=NativeFileLocks(resolved_db_path, suffix=".turn-owners",
            error_prefix="E_TURN_EXECUTION", empty_key_error="E_TURN_EXECUTION_ID_REQUIRED"),
    )


__all__ = ["build_turn_tool_control_plane_service"]
