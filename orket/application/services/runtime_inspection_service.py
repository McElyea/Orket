"""Owned runtime path, board and diagnostic observations for operator transports."""
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread


async def resolve_runtime_path(value: str | Path = ".", *, invocation_root: Path | None = None) -> Path:
    root = Path.cwd() if invocation_root is None else Path(invocation_root)
    if not root.is_absolute():
        raise ValueError("E_RUNTIME_INSPECTION_ROOT_ABSOLUTE_REQUIRED")
    path = root / value
    return await run_owned_thread(path.resolve, label="runtime-path-resolution")


async def read_runtime_board(engine: Any) -> dict[str, Any]:
    return await run_owned_thread(engine.get_board, label="runtime-board-read")


async def read_runtime_replay(
    engine: Any, *, session_id: str, issue_id: str, turn_index: int, role: str | None = None,
) -> dict[str, Any]:
    read = partial(engine.replay_turn_diagnostics, session_id=session_id, issue_id=issue_id,
                   turn_index=turn_index, role=role)
    return await run_owned_thread(read, label="runtime-replay-read")


async def read_runtime_sandbox_logs(read: Callable[[], str]) -> str:
    return await run_owned_thread(read, label="runtime-sandbox-log-read")


async def emit_runtime_manifest(emit: Callable[[str], None], department: str) -> None:
    await run_owned_thread(partial(emit, department), label="runtime-manifest")
