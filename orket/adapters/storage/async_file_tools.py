"""
Async File Tools - The Reconstruction

Provides non-blocking file I/O operations using aiofiles.
Enforces security boundaries using Path.is_relative_to().

This replaces the blocking Path.write_text and Path.read_text 
calls in the agent tools.
"""
from __future__ import annotations
import asyncio
import aiofiles
import os
import json
from pathlib import Path
from typing import Any

from .async_executor_service import run_coroutine_blocking

class AsyncFileTools:
    """
    Service for non-blocking file operations.
    """

    def __init__(self, workspace_root: Path, references: list[Path] | None = None) -> None:
        self.workspace_root = workspace_root
        self.references = references or []

    def _run_async(self, coro: Any) -> Any:
        return run_coroutine_blocking(coro)

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

        if write:
            # We enforce workspace boundaries for writes.
            # Specialized governance (like AGENT_OUTPUT_DIR) is handled by ToolGate.
            if not is_in_workspace:
                raise PermissionError(
                    f"Write access denied: {path_str} is outside the workspace."
                )

        return resolved

    async def read_file(self, path_str: str) -> str:
        """
        Read file content asynchronously.
        """
        path = self._resolve_safe_path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path_str}")

        async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
            return await f.read()

    async def write_file(self, path_str: str, content: str | dict[str, Any]) -> str:
        """
        Write content to file asynchronously.
        """
        path = self._resolve_safe_path(path_str, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not isinstance(content, str):
            content = json.dumps(content, indent=2)

        async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
            await f.write(content)
        
        return str(path)

    async def list_directory(self, path_str: str = ".") -> list[str]:
        """
        List directory contents asynchronously (using thread pool for os.listdir).
        """
        path = self._resolve_safe_path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path_str}")

        items = await asyncio.to_thread(os.listdir, path)
        return sorted(items)

    def read_file_sync(self, path_str: str) -> str:
        return self._run_async(self.read_file(path_str))

    def write_file_sync(self, path_str: str, content: str | dict[str, Any]) -> str:
        return self._run_async(self.write_file(path_str, content))

    def list_directory_sync(self, path_str: str = ".") -> list[str]:
        return self._run_async(self.list_directory(path_str))
