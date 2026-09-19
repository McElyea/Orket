"""Application-owned protocol inspection, path scope and query lifetime."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.adapters.storage.protocol_append_only_ledger import LedgerFramingError
from orket.application.services.protocol_query_scope import ProtocolQueryScope, resolve_protocol_run_root
from orket.runtime.protocol_determinism_campaign import compare_protocol_determinism_campaign
from orket.runtime.protocol_ledger_parity_campaign import compare_protocol_ledger_parity_campaign
from orket.runtime.protocol_replay import ProtocolReplayEngine
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


class ProtocolReplayService:
    """Workspace-scoped HTTP queries; explicit operator roots are CLI-only authority."""

    def __init__(self, *, workspace_root: Path, operator_invocation_root: Path | None = None) -> None:
        self._scope = ProtocolQueryScope.capture(workspace_root, operator_invocation_root)
        self._replay_engine = ProtocolReplayEngine()

    async def replay_protocol_run(
        self, *, run_id: str, events_path: str | None = None, artifact_root: str | None = None,
    ) -> dict[str, Any]:
        scope, engine = self._scope, self._replay_engine
        run_id, events_path, artifact_root = str(run_id), _token(events_path), _token(artifact_root)

        def replay() -> dict[str, Any]:
            events, artifacts = scope.replay_paths(run_id, events_path, artifact_root)
            return engine.replay_from_ledger(events_log_path=events, artifact_root=artifacts)

        return await run_owned_thread(replay, label="protocol-query-replay")

    async def compare_protocol_replays(
        self, *, run_a: str, run_b: str, events_a: str | None = None, events_b: str | None = None,
        artifacts_a: str | None = None, artifacts_b: str | None = None,
    ) -> dict[str, Any]:
        scope, engine = self._scope, self._replay_engine
        left = (str(run_a), _token(events_a), _token(artifacts_a))
        right = (str(run_b), _token(events_b), _token(artifacts_b))

        def compare() -> dict[str, Any]:
            left_events, left_artifacts = scope.replay_paths(*left)
            right_events, right_artifacts = scope.replay_paths(*right)
            return engine.compare_replays(run_a_events_path=left_events, run_b_events_path=right_events,
                run_a_artifact_root=left_artifacts, run_b_artifact_root=right_artifacts)

        return await run_owned_thread(compare, label="protocol-query-compare")

    async def compare_protocol_determinism_campaign(
        self, *, run_ids: list[str], baseline_run: str | None, runs_root: str | None,
    ) -> dict[str, Any]:
        scope, ids = self._scope, tuple(str(value) for value in run_ids or ())
        baseline, root = _token(baseline_run), _token(runs_root)
        return await run_owned_thread(lambda: compare_protocol_determinism_campaign(
            runs_root=scope.runs_path(root), run_ids=list(ids), baseline_run_id=baseline,
        ), label="protocol-query-campaign")

    async def compare_protocol_and_sqlite_run_ledgers(
        self, *, run_id: str, sqlite_db_path: str | None,
    ) -> dict[str, Any]:
        scope, session_id, sqlite_token = self._scope, str(run_id), _token(sqlite_db_path)

        def prepare() -> tuple[Path, Path]:
            resolve_protocol_run_root(scope.workspace_root, session_id)
            return scope.sqlite_path(sqlite_token), scope.workspace_root.resolve()

        sqlite, root = await run_owned_thread(prepare, label="protocol-query-parity-paths")
        return await run_owned_io(lambda: compare_run_ledger_rows(
            sqlite_repo=AsyncRunLedgerRepository(sqlite), protocol_repo=AsyncProtocolRunLedgerRepository(root),
            session_id=session_id,
        ), label="protocol-query-parity", preserve_failure=True)

    async def compare_protocol_ledger_parity_campaign(
        self, *, session_ids: list[str], sqlite_db_path: str | None, discover_limit: int,
    ) -> dict[str, Any]:
        scope, ids = self._scope, tuple(str(value) for value in session_ids or ())
        sqlite_token, limit = _token(sqlite_db_path), max(0, int(discover_limit))

        def prepare() -> tuple[Path, Path]:
            for session_id in ids:
                resolve_protocol_run_root(scope.workspace_root, session_id)
            return scope.sqlite_path(sqlite_token), scope.workspace_root.resolve()

        sqlite, root = await run_owned_thread(prepare, label="protocol-query-campaign-paths")
        return await run_owned_io(lambda: compare_protocol_ledger_parity_campaign(
            sqlite_db=sqlite, protocol_root=root, session_ids=list(ids), discover_limit=limit,
        ), label="protocol-query-parity-campaign", preserve_failure=True)


def _token(value: str | None) -> str | None:
    return str(value or "").strip() or None


__all__ = ["LedgerFramingError", "ProtocolReplayService"]
