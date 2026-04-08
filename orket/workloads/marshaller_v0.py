from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from orket.marshaller.cli import default_run_id, execute_marshaller_from_files
from orket.streaming.contracts import CommitIntent, StreamEventType
from orket.streaming.manager import InteractionContext


def _resolve_input_path(raw: str) -> Path:
    return Path(raw).resolve()


async def run_marshaller_v0(
    *,
    input_config: dict[str, Any],
    turn_params: dict[str, Any],
    interaction_context: InteractionContext,
) -> dict[str, int]:
    run_request_path = await asyncio.to_thread(
        _resolve_input_path,
        str(input_config.get("run_request_path") or "").strip(),
    )
    proposal_paths = [
        await asyncio.to_thread(_resolve_input_path, str(item))
        for item in list(input_config.get("proposal_paths") or [])
        if str(item).strip()
    ]
    workspace_root = await asyncio.to_thread(_resolve_input_path, str(input_config.get("workspace_root") or "."))
    run_id = str(input_config.get("run_id") or default_run_id()).strip()
    allowed_paths = [str(item).strip() for item in list(input_config.get("allowed_paths") or []) if str(item).strip()]
    promote = bool(input_config.get("promote", False))
    actor_id = str(input_config.get("actor_id") or "").strip() or None
    actor_source = str(input_config.get("actor_source") or "stream").strip() or "stream"
    branch = str(input_config.get("branch") or "main").strip() or "main"

    await interaction_context.emit_event(
        StreamEventType.MODEL_SELECTED,
        {"model_id": "marshaller_v0", "reason": "deterministic_local_workload", "authoritative": False},
    )
    result = await execute_marshaller_from_files(
        workspace_root=workspace_root,
        run_request_path=run_request_path,
        proposal_paths=proposal_paths,
        run_id=run_id,
        allowed_paths=allowed_paths,
        promote=promote,
        actor_id=actor_id,
        actor_source=actor_source,
        branch=branch,
    )
    await interaction_context.emit_event(
        StreamEventType.MODEL_READY,
        {
            "model_id": "marshaller_v0",
            "warm_state": "warm",
            "run_id": result["run_id"],
            "accept": bool(result["accept"]),
            "attempt_count": int(result["attempt_count"]),
            "authoritative": False,
        },
    )
    await interaction_context.emit_event(
        StreamEventType.TOKEN_DELTA,
        {
            "delta": (
                f"marshaller result: accept={bool(result['accept'])} "
                f"attempts={int(result['attempt_count'])}"
            ),
            "index": 0,
            "authoritative": False,
        },
    )
    await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref="marshaller_v0"))
    return {"post_finalize_wait_ms": 0}


def validate_marshaller_v0_start(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> None:
    run_request_raw = str(input_config.get("run_request_path") or "").strip()
    if not run_request_raw:
        raise ValueError("marshaller_v0 requires input_config.run_request_path")
    proposal_paths = [str(item).strip() for item in list(input_config.get("proposal_paths") or []) if str(item).strip()]
    if not proposal_paths:
        raise ValueError("marshaller_v0 requires input_config.proposal_paths with at least one path")
    run_request_path = Path(run_request_raw).resolve()
    if not run_request_path.exists():
        raise ValueError(f"run_request_path does not exist: {run_request_path}")
    for raw in proposal_paths:
        path = Path(raw).resolve()
        if not path.exists():
            raise ValueError(f"proposal path does not exist: {path}")
