"""Side-effecting filesystem observations; application owns their admission and lifetime."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    is_dir: bool
    suffix: str


class ApiWorkspaceReader:
    side_effecting = True

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    async def directory(self, path: str) -> tuple[DirectoryEntry, ...] | None:
        return await run_owned_thread(partial(self._directory, path), label="api-directory-observation")

    async def member_metrics_workspace(self, session_id: str) -> Path:
        return await run_owned_thread(partial(self._member_metrics_workspace, session_id), label="api-metrics-workspace")

    def _directory(self, path: str) -> tuple[DirectoryEntry, ...] | None:
        """Runs only inside the retained file worker."""
        candidate = path or "."
        if ".." in Path(candidate).parts:
            raise PermissionError("Explorer path is outside the application root.")
        relative = candidate.strip("./") if candidate != "." else ""
        target = (self.project_root/relative).resolve()
        if not target.is_relative_to(self.project_root):
            raise PermissionError("Explorer path is outside the application root.")
        if not target.exists():
            return None
        return tuple(DirectoryEntry(entry.name, entry.is_dir(), entry.suffix) for entry in target.iterdir())

    def _member_metrics_workspace(self, session_id: str) -> Path:
        """Runs only inside the retained file worker."""
        base = (self.project_root/"workspace"/"runs").resolve()
        workspace = (base/session_id).resolve()
        if not base.is_relative_to(self.project_root) or not workspace.is_relative_to(base):
            raise PermissionError("Metrics workspace is outside the runs root.")
        if workspace.exists():
            return workspace
        fallback = (self.project_root/"workspace"/"default").resolve()
        if not fallback.is_relative_to(self.project_root):
            raise PermissionError("Metrics fallback is outside the application root.")
        return fallback
