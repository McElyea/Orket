from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel, Field

from orket.application.services.protocol_replay_service import LedgerFramingError, ProtocolReplayService
from orket.core.domain import OperatorCommandClass, OperatorInputClass


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
    turn_id: str | None = None


def build_sessions_router(
    *,
    interaction_manager_getter: Callable[[], Any],
    extension_manager_getter: Callable[[], Any],
    is_builtin_workload: Callable[[str], bool],
    validate_builtin_workload_start: Callable[..., None],
    run_builtin_workload: Callable[..., Any],
    commit_intent_factory: Callable[[str], Any],
    workspace_root_getter: Callable[[], Path] = lambda: Path().resolve(),
    protocol_replay_service_getter: Callable[[], Any] | None = None,
    control_plane_publication_getter: Callable[[], Any] | None = None,
) -> APIRouter:
    router = APIRouter()

    def _workspace_root() -> Path:
        return workspace_root_getter().resolve()

    def _resolve_workspace_path(raw_path: str | Path, *, field_name: str) -> Path:
        workspace_root = _workspace_root()
        candidate = Path(str(raw_path))
        if not candidate.is_absolute():
            candidate = workspace_root / candidate
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(workspace_root):
            raise HTTPException(status_code=400, detail=f"Invalid {field_name}: path escapes workspace root.")
        return resolved

    def _get_protocol_replay_service() -> Any:
        if protocol_replay_service_getter is not None:
            return protocol_replay_service_getter()
        return ProtocolReplayService(workspace_root=_workspace_root())

    @router.post("/interactions/sessions")
    async def start_interaction_session(req: InteractionSessionStartRequest) -> dict[str, Any]:
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        session_id = await interaction_manager.start(req.session_params)
        return {"session_id": session_id}

    @router.post("/interactions/{session_id}/turns")
    async def begin_interaction_turn(
        session_id: str,
        req: InteractionTurnRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        interaction_manager = interaction_manager_getter()
        extension_manager = extension_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        workload_id = str(req.workload_id or "").strip()
        if not workload_id:
            raise HTTPException(status_code=400, detail="workload_id is required")
        has_extension_manifest_entry = extension_manager.has_manifest_entry(workload_id)
        required_capabilities: list[str] = []
        if not is_builtin_workload(workload_id) and not has_extension_manifest_entry:
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
        else:
            try:
                required_capabilities = list(extension_manager.required_capabilities_for_workload(workload_id))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        workspace = _resolve_workspace_path(req.workspace, field_name="workspace")
        context_inputs: dict[str, Any] = {
            "input_config": dict(req.input_config),
            "turn_params": dict(req.turn_params),
            "workload_id": workload_id,
            "department": str(req.department),
            "workspace": str(workspace),
        }
        if has_extension_manifest_entry:
            context_inputs["required_capabilities"] = list(required_capabilities)
        try:
            turn_id = await interaction_manager.begin_turn(
                session_id=session_id,
                input_payload=req.input_config,
                turn_params=req.turn_params,
                context_inputs=context_inputs,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        context = await interaction_manager.create_context(session_id, turn_id)

        async def _run_turn() -> None:
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

        async def _run_turn_logged() -> None:
            try:
                await _run_turn()
            except asyncio.CancelledError:
                _logger.warning("interaction turn canceled: session=%s turn=%s", session_id, turn_id)
                raise
            except (RuntimeError, ValueError, TypeError, OSError, asyncio.TimeoutError) as exc:
                _logger.error(
                    "interaction turn failed: session=%s turn=%s error=%s",
                    session_id,
                    turn_id,
                    exc,
                )
                raise

        background_tasks.add_task(_run_turn_logged)
        return {"session_id": session_id, "turn_id": turn_id}

    @router.post("/interactions/{session_id}/finalize")
    async def finalize_interaction_turn(session_id: str, req: InteractionFinalizeRequest) -> dict[str, Any]:
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        try:
            handle = await interaction_manager.finalize(session_id, req.turn_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return cast(dict[str, Any], handle.model_dump())

    @router.post("/interactions/{session_id}/cancel")
    async def cancel_interaction(
        session_id: str,
        req: InteractionCancelRequest,
        request: Request,
    ) -> dict[str, Any]:
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        target = req.turn_id or session_id
        try:
            await interaction_manager.cancel(target)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        actor_ref = str(getattr(request.state, "authenticated_actor_ref", "") or "").strip()
        if actor_ref and control_plane_publication_getter is not None:
            timestamp = datetime.now(UTC).isoformat()
            target_ref = f"interaction-turn:{target}" if req.turn_id else f"interaction-session:{session_id}"
            affected_resource_refs = [f"interaction-session:{session_id}"]
            if req.turn_id:
                affected_resource_refs.append(target_ref)
            publication = control_plane_publication_getter()
            await publication.publish_operator_action(
                action_id=f"interaction-operator-action:{session_id}:{target}:{timestamp}",
                actor_ref=actor_ref,
                input_class=OperatorInputClass.COMMAND,
                target_ref=target_ref,
                timestamp=timestamp,
                precondition_basis_ref=f"{target_ref}:cancel_requested",
                result="accepted_cancel",
                command_class=OperatorCommandClass.CANCEL_RUN,
                affected_transition_refs=[f"{target_ref}:cancel_requested"],
                affected_resource_refs=affected_resource_refs,
                receipt_refs=[f"interaction-cancel:{target}"],
            )
        return {"ok": True, "target": target}

    @router.get("/marshaller/runs")
    async def list_marshaller_run_rows(limit: int = 20) -> dict[str, Any]:
        from orket.marshaller.cli import list_marshaller_runs

        workspace_root = _workspace_root()
        rows = await list_marshaller_runs(workspace_root, limit=max(1, int(limit)))
        return {"runs": rows}

    @router.get("/marshaller/runs/{run_id}")
    async def inspect_marshaller_run(run_id: str, attempt_index: int | None = None) -> Any:
        from orket.marshaller.cli import inspect_marshaller_attempt

        workspace_root = _workspace_root()
        try:
            return await inspect_marshaller_attempt(
                workspace_root,
                run_id=run_id,
                attempt_index=attempt_index,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/protocol/runs/{run_id}/replay")
    async def replay_protocol_run(run_id: str) -> Any:
        try:
            replay = await _get_protocol_replay_service().replay_protocol_run(run_id=run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except LedgerFramingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return replay

    @router.get("/protocol/replay/compare")
    async def compare_protocol_replays(run_a: str, run_b: str) -> Any:
        try:
            comparison = await _get_protocol_replay_service().compare_protocol_replays(run_a=run_a, run_b=run_b)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except LedgerFramingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return comparison

    @router.get("/protocol/replay/campaign")
    async def campaign_protocol_replays(
        run_id: Annotated[list[str] | None, Query()] = None,
        baseline_run: str | None = None,
        runs_root: str | None = None,
    ) -> Any:
        try:
            return await _get_protocol_replay_service().compare_protocol_determinism_campaign(
                run_ids=list(run_id or []),
                baseline_run=baseline_run,
                runs_root=runs_root,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/protocol/runs/{run_id}/ledger-parity")
    async def compare_protocol_and_sqlite_run_ledgers(run_id: str, sqlite_db_path: str | None = None) -> Any:
        try:
            return await _get_protocol_replay_service().compare_protocol_and_sqlite_run_ledgers(
                run_id=run_id,
                sqlite_db_path=sqlite_db_path,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except LedgerFramingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/protocol/ledger-parity/campaign")
    async def campaign_protocol_ledger_parity(
        session_id: Annotated[list[str] | None, Query()] = None,
        sqlite_db_path: str | None = None,
        discover_limit: int = 200,
    ) -> Any:
        try:
            return await _get_protocol_replay_service().compare_protocol_ledger_parity_campaign(
                session_ids=list(session_id or []),
                sqlite_db_path=sqlite_db_path,
                discover_limit=discover_limit,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
