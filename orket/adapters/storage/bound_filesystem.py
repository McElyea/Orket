"""Handle-owned execution of an application-authorized filesystem target."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.core.domain.outward_authorization import OutwardAuthorization, args_hash

BOUND_FILESYSTEM_TOOLS = frozenset({"read_file", "write_file", "create_directory", "delete_file"})


class BoundFilesystemExecutor:
    side_effecting = True

    async def invoke(self, binding: OutwardAuthorization, args: dict[str, Any]) -> dict[str, Any]:
        if binding.tool not in BOUND_FILESYSTEM_TOOLS or args_hash(args) != binding.arguments_digest:
            raise RuntimeError("E_OUTWARD_AUTHORIZATION_ARGUMENT_DRIFT")
        return await run_owned_io(lambda: asyncio.to_thread(_execute, binding, args), label="bound filesystem")


def _execute(binding: OutwardAuthorization, args: dict[str, Any]) -> dict[str, Any]:
    """Runs exclusively in the owned thread; no path-based I/O after acquiring the target."""
    root, target = Path(binding.workspace_root), Path(binding.target_ref)
    if (not root.is_absolute() or not target.is_absolute() or not target.is_relative_to(root)
            or (target == root and binding.tool != "create_directory")):
        raise RuntimeError("E_OUTWARD_AUTHORIZATION_TARGET_DRIFT")
    requested = Path(str(args["path"]))
    if not requested.is_absolute():
        requested = root / requested
    if root.resolve() != root or requested.resolve() != target:
        raise RuntimeError("E_OUTWARD_AUTHORIZATION_TARGET_DRIFT")
    if os.name == "nt":
        from orket.adapters.storage.bound_filesystem_windows import open_target
    elif os.name == "posix":
        from orket.adapters.storage.bound_filesystem_posix import open_target
    else:
        raise RuntimeError("E_OUTWARD_BOUND_FILESYSTEM_HOST_UNSUPPORTED")
    try:
        with open_target(root, target, requested, operation=binding.tool) as (descriptor, delete):
            return _operate(binding.tool, args, target, descriptor, delete)
    except (PermissionError, OSError, ValueError, TypeError) as exc:
        return {"ok": False, "error": str(exc)}


def _operate(tool, args, target, descriptor, delete):
    if tool == "read_file":
        with os.fdopen(os.dup(descriptor), "r", encoding="utf-8") as stream:
            return {"ok": True, "content": stream.read()}
    if tool == "write_file":
        content = args["content"]
        if not isinstance(content, str):
            content = json.dumps(content, indent=2)
        # Truncate only after the opened handle has passed no-follow/type checks.
        os.ftruncate(descriptor, 0)
        with os.fdopen(os.dup(descriptor), "w", encoding="utf-8") as stream:
            stream.write(content)
    elif tool == "delete_file":
        delete()
    elif tool != "create_directory":
        raise ValueError("Unsupported bound filesystem operation")
    return {"ok": True, "path": str(target)}
