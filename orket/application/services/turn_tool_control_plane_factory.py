from __future__ import annotations

from pathlib import Path

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
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
    )


__all__ = ["build_turn_tool_control_plane_service"]
