from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import AsyncFileTools, capture_file_roots
from orket.logging import log_event

from .turn_path_resolver import PathResolver

_MAX_PRELOADED_READ_CONTEXT_CHARS = 4000


@dataclass(frozen=True)
class RequiredReadObservation:
    existing: tuple[str, ...]
    missing: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "existing", tuple(self.existing))
        object.__setattr__(self, "missing", tuple(self.missing))


async def observe_required_read_paths(
    *, context: dict[str, Any], workspace: Path,
) -> RequiredReadObservation:
    required_paths = PathResolver.normalized_required_read_paths(context)
    if not required_paths:
        return RequiredReadObservation(existing=(), missing=())
    captured_workspace, = capture_file_roots([workspace])
    existing, missing = await run_owned_thread(
        partial(PathResolver.partition_governed_required_read_paths, required_paths, captured_workspace),
        label="turn-required-read-metadata",
    )
    return RequiredReadObservation(existing=existing, missing=missing)


async def observe_legacy_required_read_paths(
    *, context: dict[str, Any], workspace: Path,
) -> RequiredReadObservation:
    required_paths = PathResolver.normalized_required_read_paths(context)
    if not required_paths:
        return RequiredReadObservation(existing=(), missing=())
    captured_workspace, = capture_file_roots([workspace])
    existing, missing = await run_owned_thread(
        partial(PathResolver.partition_required_read_paths, required_paths, captured_workspace),
        label="turn-legacy-required-read-metadata",
    )
    return RequiredReadObservation(existing=existing, missing=missing)


async def observe_available_required_read_paths(
    *, required_paths: Sequence[Any], workspace: Path,
) -> tuple[str, ...]:
    captured_paths = PathResolver.normalized_required_read_paths({"required_read_paths": required_paths})
    if not captured_paths:
        return ()
    captured_workspace, = capture_file_roots([workspace])
    return await run_owned_thread(
        partial(PathResolver.available_required_read_paths, captured_paths, captured_workspace),
        label="turn-available-required-read-metadata",
    )


async def observe_workspace_constraint_violation(
    *, tool_name: str, args: dict[str, Any], workspace: Path,
) -> str | None:
    captured_tool = str(tool_name or "").strip()
    if not PathResolver.is_path_tool(captured_tool):
        return None
    captured_args = {"path": str(args.get("path", "")).strip()} if isinstance(args, dict) else args
    if not isinstance(captured_args, dict) or not captured_args["path"]:
        return PathResolver.workspace_constraint_violation(
            tool_name=captured_tool, args=captured_args, workspace=workspace,
        )
    captured_workspace, = capture_file_roots([workspace])
    return await run_owned_thread(
        partial(
            PathResolver.workspace_constraint_violation,
            tool_name=captured_tool,
            args=captured_args,
            workspace=captured_workspace,
        ),
        label="turn-submitted-path-metadata",
    )


async def preload_required_read_context(
    *, required_read_paths: list[str], workspace: Path,
) -> list[str]:
    rendered: list[str] = []
    files = AsyncFileTools(workspace).capture()
    for rel_path in required_read_paths:
        candidate = await files.resolve_path_async(rel_path)
        is_file = await run_owned_thread(
            lambda candidate=candidate: candidate.exists() and candidate.is_file(),
            label="turn-required-read-file-type",
        )
        if not is_file:
            continue
        content = await files.read_file(rel_path)
        normalized = content.replace("\r\n", "\n")
        truncated = len(normalized) > _MAX_PRELOADED_READ_CONTEXT_CHARS
        if truncated:
            normalized = normalized[:_MAX_PRELOADED_READ_CONTEXT_CHARS]
        block = f"Path: {rel_path}\nContent:\n{normalized}"
        rendered.append(block + ("\n[truncated]" if truncated else ""))
    return rendered


async def publish_missing_read_event(
    *, issue_id: str, role_name: str, session_id: Any, turn_index: Any,
    missing_required_read_paths: list[str], workspace: Path,
) -> None:
    missing = list(missing_required_read_paths)
    payload = {
        "issue_id": issue_id,
        "role": role_name,
        "session_id": session_id,
        "turn_index": int(turn_index),
        "missing_required_read_paths_count": len(missing),
        "missing_required_read_paths": missing,
    }
    await run_owned_thread(
        partial(log_event, "preflight_missing_read_paths", payload, workspace),
        label="turn-missing-read-log",
    )
