from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.logging import log_event

from .turn_path_resolver import PathResolver

_MAX_PRELOADED_READ_CONTEXT_CHARS = 4000


@dataclass(frozen=True)
class RequiredReadObservation:
    existing: list[str]
    missing: list[str]


async def observe_required_read_paths(
    *, context: dict[str, Any], workspace: Path,
) -> RequiredReadObservation:
    existing, missing = await run_owned_thread(
        partial(PathResolver.partition_governed_required_read_paths, context, workspace),
        label="turn-required-read-metadata",
    )
    return RequiredReadObservation(existing=existing, missing=missing)


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
