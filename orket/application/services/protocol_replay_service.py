from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.adapters.storage.protocol_append_only_ledger import LedgerFramingError
from orket.runtime.protocol_determinism_campaign import compare_protocol_determinism_campaign
from orket.runtime.protocol_ledger_parity_campaign import compare_protocol_ledger_parity_campaign
from orket.runtime.protocol_replay import ProtocolReplayEngine
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


class ProtocolReplayService:
    """Application boundary for protocol replay and run-ledger parity queries."""

    def __init__(self, *, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self._replay_engine = ProtocolReplayEngine()

    async def replay_protocol_run(self, *, run_id: str) -> dict[str, Any]:
        run_root = self._resolve_protocol_run_root(run_id)
        events_path = run_root / "events.log"
        if not events_path.exists():
            raise FileNotFoundError(f"Protocol events log not found for run '{run_id}'.")
        artifact_root = run_root / "artifacts"
        return await asyncio.to_thread(
            self._replay_engine.replay_from_ledger,
            events_log_path=events_path,
            artifact_root=artifact_root if artifact_root.exists() else None,
        )

    async def compare_protocol_replays(self, *, run_a: str, run_b: str) -> dict[str, Any]:
        run_a_root = self._resolve_protocol_run_root(run_a)
        run_b_root = self._resolve_protocol_run_root(run_b)
        run_a_events = run_a_root / "events.log"
        run_b_events = run_b_root / "events.log"
        if not run_a_events.exists():
            raise FileNotFoundError(f"Protocol events log not found for run '{run_a}'.")
        if not run_b_events.exists():
            raise FileNotFoundError(f"Protocol events log not found for run '{run_b}'.")

        run_a_artifacts = run_a_root / "artifacts"
        run_b_artifacts = run_b_root / "artifacts"
        return await asyncio.to_thread(
            self._replay_engine.compare_replays,
            run_a_events_path=run_a_events,
            run_b_events_path=run_b_events,
            run_a_artifact_root=run_a_artifacts if run_a_artifacts.exists() else None,
            run_b_artifact_root=run_b_artifacts if run_b_artifacts.exists() else None,
        )

    async def compare_protocol_determinism_campaign(
        self,
        *,
        run_ids: list[str],
        baseline_run: str | None,
        runs_root: str | None,
    ) -> dict[str, Any]:
        runs_root_token = str(runs_root or "").strip()
        root = (
            self._resolve_workspace_path(runs_root_token, field_name="runs_root")
            if runs_root_token
            else (self.workspace_root / "runs").resolve()
        )
        if not root.exists():
            raise FileNotFoundError(f"Runs root not found: {root}")
        return await asyncio.to_thread(
            compare_protocol_determinism_campaign,
            runs_root=root,
            run_ids=list(run_ids or []),
            baseline_run_id=str(baseline_run or "").strip() or None,
        )

    async def compare_protocol_and_sqlite_run_ledgers(
        self,
        *,
        run_id: str,
        sqlite_db_path: str | None,
    ) -> dict[str, Any]:
        _ = self._resolve_protocol_run_root(run_id)
        sqlite_path = self._resolve_sqlite_path(sqlite_db_path)
        sqlite_repo = AsyncRunLedgerRepository(sqlite_path)
        protocol_repo = AsyncProtocolRunLedgerRepository(self.workspace_root)
        return await compare_run_ledger_rows(
            sqlite_repo=sqlite_repo,
            protocol_repo=protocol_repo,
            session_id=str(run_id),
        )

    async def compare_protocol_ledger_parity_campaign(
        self,
        *,
        session_ids: list[str],
        sqlite_db_path: str | None,
        discover_limit: int,
    ) -> dict[str, Any]:
        sqlite_path = self._resolve_sqlite_path(sqlite_db_path)
        return await compare_protocol_ledger_parity_campaign(
            sqlite_db=sqlite_path,
            protocol_root=self.workspace_root,
            session_ids=list(session_ids or []),
            discover_limit=max(0, int(discover_limit)),
        )

    def _resolve_sqlite_path(self, raw_path: str | None) -> Path:
        sqlite_path_token = str(raw_path or "").strip()
        sqlite_path = (
            self._resolve_workspace_path(sqlite_path_token, field_name="sqlite_db_path")
            if sqlite_path_token
            else (self.workspace_root / ".orket" / "durable" / "db" / "orket_persistence.db").resolve()
        )
        if not sqlite_path.exists():
            raise FileNotFoundError(f"SQLite run ledger database not found: {sqlite_path}")
        return sqlite_path

    def _resolve_workspace_path(self, raw_path: str | Path, *, field_name: str) -> Path:
        candidate = Path(str(raw_path))
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self.workspace_root):
            raise ValueError(f"Invalid {field_name}: path escapes workspace root.")
        return resolved

    def _resolve_protocol_run_root(self, run_id: str) -> Path:
        base = (self.workspace_root / "runs").resolve()
        candidate = (base / str(run_id).strip()).resolve()
        if not candidate.is_relative_to(base):
            raise ValueError("Invalid run_id")
        return candidate


__all__ = ["LedgerFramingError", "ProtocolReplayService"]
