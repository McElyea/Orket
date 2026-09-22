"""Own asynchronous file operations and capture their standard path permissions.

Native path traversal and file work stay owned through caller interruption.
Resolved-path containment is not handle-bound confinement against replacement.
"""

from __future__ import annotations

import json
import os
from collections.abc import Coroutine
from copy import copy
from functools import partial
from pathlib import Path
from typing import Any, TypeVar

import aiofiles

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread

from .async_executor_service import run_coroutine_blocking

ResultT = TypeVar("ResultT")
side_effecting = True


def capture_file_roots(paths: list[Path]) -> list[Path]:
    """Bind standard filesystem roots before an invocation first yields."""
    roots = [Path(path) for path in paths]
    if any(path.drive and not path.is_absolute() for path in roots):
        raise ValueError("E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED")
    invocation_root = Path.cwd() if any(not path.is_absolute() for path in roots) else None
    return [invocation_root / path if not path.is_absolute() else path for path in roots]


class AsyncFileTools:
    """
    Service for non-blocking file operations.
    """

    def __init__(self, workspace_root: Path, references: list[Path] | None = None) -> None:
        self.workspace_root = workspace_root
        self.references = references or []

    def _run_async(self, coro: Coroutine[Any, Any, ResultT]) -> ResultT:
        return run_coroutine_blocking(coro)

    def capture(self) -> AsyncFileTools:
        """Copy path permissions and bind relative roots before the first await."""
        bound = capture_file_roots([self.workspace_root, *self.references])
        captured = copy(self)
        captured.workspace_root, captured.references = bound[0], bound[1:]
        return captured

    @staticmethod
    def _serialized_content(content: str | dict[str, Any]) -> str:
        return content if isinstance(content, str) else json.dumps(content, indent=2)

    async def resolve_path_async(self, path_str: str, *, write: bool = False) -> Path:
        captured = self.capture()
        return await run_owned_thread(partial(captured._resolve_safe_path, path_str, write=write), label="file-path")

    def _resolve_safe_path(self, path_str: str, write: bool = False) -> Path:
        """
        Secure path validation.
        """
        p = Path(path_str)
        if not p.is_absolute():
            p = self.workspace_root / p

        resolved = p.resolve(strict=False)
        workspace_resolved = self.workspace_root.resolve()

        # Check if within workspace
        try:
            is_in_workspace = resolved.is_relative_to(workspace_resolved)
        except ValueError:
            is_in_workspace = False

        # Check if within references (read-only)
        is_in_references = False
        for ref in self.references:
            try:
                if resolved.is_relative_to(ref.resolve()):
                    is_in_references = True
                    break
            except ValueError:
                continue

        if not (is_in_workspace or is_in_references):
            raise PermissionError(f"Access denied: {path_str} is outside allowed boundaries.")

        if write and not is_in_workspace:
            # We enforce workspace boundaries for writes.
            # Specialized governance (like AGENT_OUTPUT_DIR) is handled by ToolGate.
            raise PermissionError(f"Write access denied: {path_str} is outside the workspace.")

        return resolved

    async def read_file(self, path_str: str) -> str:
        return await self._operate("read", path_str)

    async def write_file(self, path_str: str, content: str | dict[str, Any]) -> str:
        return await self._operate("write", path_str, content=self._serialized_content(content))

    async def create_directory(self, path_str: str) -> str:
        return await self._operate("create", path_str)

    async def list_directory(self, path_str: str = ".") -> list[str]:
        return await self._operate("list", path_str)

    async def _operate(self, operation: str, path_str: str, *, content: str | None = None):
        captured = self.capture()

        async def execute():
            path = await captured.resolve_path_async(path_str, write=operation in {"write", "create"})
            if operation in {"read", "list"} and not await run_owned_thread(path.exists, label="file-exists"):
                kind = "File" if operation == "read" else "Directory"
                raise FileNotFoundError(f"{kind} not found: {path_str}")
            if operation == "read":
                async with aiofiles.open(path, encoding="utf-8") as stream:
                    return await stream.read()
            if operation == "write":
                await run_owned_thread(partial(path.parent.mkdir, parents=True, exist_ok=True), label="file-parent")
                async with aiofiles.open(path, mode="w", encoding="utf-8") as stream:
                    await stream.write(content)
                return str(path)
            if operation == "create":
                await run_owned_thread(partial(path.mkdir, parents=True, exist_ok=True), label="file-directory")
                return str(path)
            if operation == "list":
                return sorted(await run_owned_thread(partial(os.listdir, path), label="file-list"))
            raise ValueError("E_FILE_TOOL_OPERATION_UNSUPPORTED")

        return await run_owned_io(execute, label=f"file-{operation}", preserve_failure=True)

    def read_file_sync(self, path_str: str) -> str:
        return self._run_async(self.read_file(path_str))

    def write_file_sync(self, path_str: str, content: str | dict[str, Any]) -> str:
        return self._run_async(self.write_file(path_str, content))

    def create_directory_sync(self, path_str: str) -> str:
        return self._run_async(self.create_directory(path_str))

    def list_directory_sync(self, path_str: str = ".") -> list[str]:
        return self._run_async(self.list_directory(path_str))
