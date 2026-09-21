"""Owned preparation and synchronous worker composition of extension execution stores."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import require_sync_context, run_owned_thread
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.extension_workload_control_plane_service import ExtensionWorkloadControlPlaneService
from orket.time_utils import utc_now_iso


def build_extension_workload_control_plane_service(
    *,
    project_root: Path,
    db_path: str | Path | None = None,
    utc_now: Callable[[], str] = utc_now_iso,
) -> ExtensionWorkloadControlPlaneService:
    require_sync_context(code="E_EXT_CONTROL_PLANE_CONSTRUCTION_REQUIRES_WORKER")
    selected = (
        Path(db_path)
        if db_path is not None
        else project_root / ".orket" / "durable" / "db" / "control_plane_records.sqlite3"
    )
    resolved_db_path = selected if selected.is_absolute() else Path.cwd() / selected
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
    return ExtensionWorkloadControlPlaneService(
        execution_repository=AsyncControlPlaneExecutionRepository(resolved_db_path),
        publication=ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path)),
        transactions=SQLiteControlPlaneTransactions(resolved_db_path),
        utc_now=utc_now,
    )


async def prepare_extension_workload_control_plane_service(
    *,
    project_root: Path,
    db_path: str | Path | None = None,
    invocation_root: Path | None = None,
    utc_now: Callable[[], str] = utc_now_iso,
) -> ExtensionWorkloadControlPlaneService:
    """Capture relative locations before retaining the native construction worker."""
    root = invocation_root or Path.cwd()
    if not root.is_absolute():
        raise ValueError("E_EXT_INVOCATION_ROOT_ABSOLUTE_REQUIRED")
    project = root / project_root
    database = root / db_path if db_path is not None else None
    return await run_owned_thread(
        partial(build_extension_workload_control_plane_service, project_root=project, db_path=database, utc_now=utc_now),
        label="extension-control-plane-construction",
    )
