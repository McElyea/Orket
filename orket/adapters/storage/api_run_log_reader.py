"""Owned native reads for diagnostic run observations; no completion authority."""
from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread

side_effecting = True


class ApiRunLogReader:
    side_effecting = True

    def __init__(self, project_root: Path) -> None:
        if not project_root.is_absolute():
            raise ValueError("E_API_RUN_ROOT_ABSOLUTE_REQUIRED")
        self.project_root = project_root

    async def records(self, session_id: str | None, *, run_first: bool = False) -> list[dict[str, Any]]:
        return await run_owned_thread(partial(self._records, session_id, run_first), label="api-run-log-read")

    async def run_path(self, session_id: str) -> Path:
        return await run_owned_thread(partial(self._run_path, session_id), label="api-run-path")

    def _contained(self, path: Path, root: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise PermissionError("Run observation path is outside its declared root.")
        return resolved

    def _run_path(self, session_id: str) -> Path:
        base = self._contained(self.project_root / "workspace/runs", self.project_root)
        return self._contained(base / session_id, base)

    def _records(self, session_id: str | None, run_first: bool) -> list[dict[str, Any]]:
        default = self._contained(self.project_root / "workspace/default", self.project_root)
        roots = [default]
        if session_id:
            roots.append(self._run_path(session_id))
        if run_first:
            roots.reverse()
        paths = [self._contained(root / "orket.log", root) for root in roots]
        records: list[dict[str, Any]] = []
        for path in paths:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
        return records
