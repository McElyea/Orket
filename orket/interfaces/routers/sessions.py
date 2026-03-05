from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.adapters.storage.protocol_append_only_ledger import LedgerFramingError
from orket.runtime.protocol_determinism_campaign import compare_protocol_determinism_campaign
from orket.runtime.protocol_ledger_parity_campaign import compare_protocol_ledger_parity_campaign
from orket.runtime.protocol_replay import ProtocolReplayEngine
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


class InteractionSessionStartRequest(BaseModel):
    session_params: dict[str, Any] = Field(default_factory=dict)


class InteractionTurnRequest(BaseModel):
    workload_id: str
    input_config: dict[str, Any] = Field(default_factory=dict)
    department: str = "core"
    workspace: str = "workspace/default"
    turn_params: dict[str, Any] = Field(default_factory=dict)


class InteractionFinalizeRequest(BaseModel):
    turn_id: str


class InteractionCancelRequest(BaseModel):
    turn_id: Optional[str] = None


def build_sessions_router(
    *,
    interaction_manager_getter: Callable[[], Any],
    extension_manager_getter: Callable[[], Any],
    is_builtin_workload: Callable[[str], bool],
    validate_builtin_workload_start: Callable[..., None],
    run_builtin_workload: Callable[..., Any],
    commit_intent_factory: Callable[[str], Any],
    workspace_root_getter: Callable[[], Path] = lambda: Path(".").resolve(),
) -> APIRouter:
    router = APIRouter()

    def _resolve_protocol_run_root(run_id: str) -> Path:
        base = (workspace_root_getter() / "runs").resolve()
        candidate = (base / str(run_id).strip()).resolve()
        if not candidate.is_relative_to(base):
            raise HTTPException(status_code=400, detail="Invalid run_id")
        return candidate

    @router.post("/interactions/sessions")
    async def start_interaction_session(req: InteractionSessionStartRequest):
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        session_id = await interaction_manager.start(req.session_params)
        return {"session_id": session_id}

    @router.post("/interactions/{session_id}/turns")
    async def begin_interaction_turn(session_id: str, req: InteractionTurnRequest):
        interaction_manager = interaction_manager_getter()
        extension_manager = extension_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        workload_id = str(req.workload_id or "").strip()
        if not workload_id:
            raise HTTPException(status_code=400, detail="workload_id is required")
        extension_match = extension_manager.resolve_workload(workload_id)
        if not is_builtin_workload(workload_id) and extension_match is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown workload '{workload_id}'. Built-in workloads: "
                    "stream_test_v1, model_stream_v1, rulesim_v0, marshaller_v0."
                ),
            )
        if is_builtin_workload(workload_id):
            try:
                validate_builtin_workload_start(
                    workload_id=workload_id,
                    input_config=req.input_config,
                    turn_params=req.turn_params,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            turn_id = await interaction_manager.begin_turn(
                session_id=session_id,
                input_payload=req.input_config,
                turn_params=req.turn_params,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        context = await interaction_manager.create_context(session_id, turn_id)
        workspace = Path(req.workspace).resolve()

        async def _run_turn():
            try:
                if is_builtin_workload(workload_id):
                    hints = await run_builtin_workload(
                        workload_id=workload_id,
                        input_config=req.input_config,
                        turn_params=req.turn_params,
                        interaction_context=context,
                    )
                    if int(hints.get("request_cancel_turn", 0) or 0) > 0:
                        await interaction_manager.cancel(turn_id)
                    await interaction_manager.finalize(session_id, turn_id)
                    post_finalize_wait_ms = int(hints.get("post_finalize_wait_ms", 0))
                    if post_finalize_wait_ms > 0:
                        await asyncio.sleep(post_finalize_wait_ms / 1000.0)
                else:
                    await extension_manager.run_workload(
                        workload_id=workload_id,
                        input_config=req.input_config,
                        workspace=workspace,
                        department=req.department,
                        interaction_context=context,
                    )
                    await interaction_manager.finalize(session_id, turn_id)
            except (RuntimeError, ValueError, TypeError, OSError, asyncio.TimeoutError) as exc:
                await interaction_manager.cancel(turn_id)
                await context.request_commit(commit_intent_factory(str(exc)))
                await interaction_manager.finalize(session_id, turn_id)

        _logger = logging.getLogger(__name__)
        def _log_turn_failure(done_task: asyncio.Task[Any]) -> None:
            try:
                error = done_task.exception()
            except asyncio.CancelledError:
                return
            if error is not None:
                _logger.error(
                    "interaction turn failed: session=%s turn=%s error=%s",
                    session_id,
                    turn_id,
                    error,
                )

        task = asyncio.create_task(_run_turn())
        task.add_done_callback(_log_turn_failure)
        return {"session_id": session_id, "turn_id": turn_id}

    @router.post("/interactions/{session_id}/finalize")
    async def finalize_interaction_turn(session_id: str, req: InteractionFinalizeRequest):
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        try:
            handle = await interaction_manager.finalize(session_id, req.turn_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return handle.model_dump()

    @router.post("/interactions/{session_id}/cancel")
    async def cancel_interaction(session_id: str, req: InteractionCancelRequest):
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        target = req.turn_id or session_id
        try:
            await interaction_manager.cancel(target)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "target": target}

    @router.get("/marshaller/runs")
    async def list_marshaller_run_rows(limit: int = 20):
        from orket.marshaller.cli import list_marshaller_runs

        workspace_root = workspace_root_getter()
        rows = await list_marshaller_runs(workspace_root, limit=max(1, int(limit)))
        return {"runs": rows}

    @router.get("/marshaller/runs/{run_id}")
    async def inspect_marshaller_run(run_id: str, attempt_index: Optional[int] = None):
        from orket.marshaller.cli import inspect_marshaller_attempt

        workspace_root = workspace_root_getter()
        try:
            return await inspect_marshaller_attempt(
                workspace_root,
                run_id=run_id,
                attempt_index=attempt_index,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/protocol/runs/{run_id}/replay")
    async def replay_protocol_run(run_id: str):
        run_root = _resolve_protocol_run_root(run_id)
        events_path = run_root / "events.log"
        if not events_path.exists():
            raise HTTPException(status_code=404, detail=f"Protocol events log not found for run '{run_id}'.")
        artifact_root = run_root / "artifacts"
        engine = ProtocolReplayEngine()
        try:
            replay = await asyncio.to_thread(
                engine.replay_from_ledger,
                events_log_path=events_path,
                artifact_root=artifact_root if artifact_root.exists() else None,
            )
        except LedgerFramingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return replay

    @router.get("/protocol/replay/compare")
    async def compare_protocol_replays(run_a: str, run_b: str):
        run_a_root = _resolve_protocol_run_root(run_a)
        run_b_root = _resolve_protocol_run_root(run_b)
        run_a_events = run_a_root / "events.log"
        run_b_events = run_b_root / "events.log"
        if not run_a_events.exists():
            raise HTTPException(status_code=404, detail=f"Protocol events log not found for run '{run_a}'.")
        if not run_b_events.exists():
            raise HTTPException(status_code=404, detail=f"Protocol events log not found for run '{run_b}'.")

        run_a_artifacts = run_a_root / "artifacts"
        run_b_artifacts = run_b_root / "artifacts"
        engine = ProtocolReplayEngine()
        try:
            comparison = await asyncio.to_thread(
                engine.compare_replays,
                run_a_events_path=run_a_events,
                run_b_events_path=run_b_events,
                run_a_artifact_root=run_a_artifacts if run_a_artifacts.exists() else None,
                run_b_artifact_root=run_b_artifacts if run_b_artifacts.exists() else None,
            )
        except LedgerFramingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return comparison

    @router.get("/protocol/replay/campaign")
    async def campaign_protocol_replays(
        run_id: list[str] = Query(default_factory=list),
        baseline_run: Optional[str] = None,
        runs_root: Optional[str] = None,
    ):
        root = (
            Path(str(runs_root)).resolve()
            if str(runs_root or "").strip()
            else (workspace_root_getter() / "runs").resolve()
        )
        if not root.exists():
            raise HTTPException(status_code=404, detail=f"Runs root not found: {root}")
        try:
            return await asyncio.to_thread(
                compare_protocol_determinism_campaign,
                runs_root=root,
                run_ids=list(run_id or []),
                baseline_run_id=str(baseline_run or "").strip() or None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/protocol/runs/{run_id}/ledger-parity")
    async def compare_protocol_and_sqlite_run_ledgers(run_id: str, sqlite_db_path: Optional[str] = None):
        _ = _resolve_protocol_run_root(run_id)
        sqlite_path = (
            Path(str(sqlite_db_path)).resolve()
            if str(sqlite_db_path or "").strip()
            else (workspace_root_getter() / ".orket" / "durable" / "db" / "orket_persistence.db").resolve()
        )
        if not sqlite_path.exists():
            raise HTTPException(status_code=404, detail=f"SQLite run ledger database not found: {sqlite_path}")
        protocol_root = workspace_root_getter()
        sqlite_repo = AsyncRunLedgerRepository(sqlite_path)
        protocol_repo = AsyncProtocolRunLedgerRepository(protocol_root)
        try:
            return await compare_run_ledger_rows(
                sqlite_repo=sqlite_repo,
                protocol_repo=protocol_repo,
                session_id=str(run_id),
            )
        except LedgerFramingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/protocol/ledger-parity/campaign")
    async def campaign_protocol_ledger_parity(
        session_id: list[str] = Query(default_factory=list),
        sqlite_db_path: Optional[str] = None,
        discover_limit: int = 200,
    ):
        sqlite_path = (
            Path(str(sqlite_db_path)).resolve()
            if str(sqlite_db_path or "").strip()
            else (workspace_root_getter() / ".orket" / "durable" / "db" / "orket_persistence.db").resolve()
        )
        if not sqlite_path.exists():
            raise HTTPException(status_code=404, detail=f"SQLite run ledger database not found: {sqlite_path}")
        try:
            return await compare_protocol_ledger_parity_campaign(
                sqlite_db=sqlite_path,
                protocol_root=workspace_root_getter(),
                session_ids=list(session_id or []),
                discover_limit=max(0, int(discover_limit)),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
