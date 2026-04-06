from __future__ import annotations

import asyncio
from collections import OrderedDict
from pathlib import Path
from typing import Any

from orket.adapters.tools.families.base import BaseTools

_MAX_PATH_LOCKS = 1024


class FileSystemTools(BaseTools):
    def __init__(self, workspace_root: Path, references: list[Path]):
        super().__init__(workspace_root, references)
        from orket.adapters.storage.async_file_tools import AsyncFileTools

        self.async_fs = AsyncFileTools(workspace_root, references)
        self._path_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()

    def _get_path_lock(self, resolved_path: Path) -> asyncio.Lock:
        key = str(resolved_path)
        lock = self._path_locks.get(key)
        if lock is not None:
            self._path_locks.move_to_end(key)
            return lock
        lock = asyncio.Lock()
        self._path_locks[key] = lock
        while len(self._path_locks) > _MAX_PATH_LOCKS:
            self._path_locks.popitem(last=False)
        return lock

    @staticmethod
    def _require_path_arg(args: dict[str, Any]) -> str:
        path_value = args.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("path is required")
        return path_value

    @staticmethod
    def _require_write_content(args: dict[str, Any]) -> str | dict[str, Any]:
        content = args.get("content")
        if isinstance(content, (str, dict)):
            return content
        raise TypeError("content must be a string or object")

    async def read_file(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            path_str = self._require_path_arg(args)
            content = await self.async_fs.read_file(path_str)
            return {"ok": True, "content": content}
        except FileNotFoundError:
            return {"ok": False, "error": "File not found"}
        except (PermissionError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def write_file(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            path_str = self._require_path_arg(args)
            content = self._require_write_content(args)
            resolved = self.async_fs._resolve_safe_path(path_str, write=True)
            lock = self._get_path_lock(resolved)
            async with lock:
                path = await self.async_fs.write_file(str(resolved), content)
            return {"ok": True, "path": path}
        except (PermissionError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def list_directory(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            raw_path = args.get("path", ".")
            if not isinstance(raw_path, str):
                raise TypeError("path must be a string")
            path_str = raw_path
            items = await self.async_fs.list_directory(path_str)
            return {"ok": True, "items": items}
        except FileNotFoundError:
            return {"ok": False, "error": "Dir not found"}
        except (PermissionError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}
