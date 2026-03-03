from __future__ import annotations

import asyncio
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List

from orket.adapters.tools.families.base import BaseTools

_MAX_PATH_LOCKS = 1024


class FileSystemTools(BaseTools):

    def __init__(self, workspace_root: Path, references: List[Path]):
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

    async def read_file(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path_str = args.get("path")
            content = await self.async_fs.read_file(path_str)
            return {"ok": True, "content": content}
        except FileNotFoundError:
            return {"ok": False, "error": "File not found"}
        except (PermissionError, FileNotFoundError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def write_file(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path_str = args.get("path")
            content = args.get("content")
            resolved = self.async_fs._resolve_safe_path(path_str, write=True)
            lock = self._get_path_lock(resolved)
            async with lock:
                path = await self.async_fs.write_file(str(resolved), content)
            return {"ok": True, "path": path}
        except (PermissionError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def list_directory(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path_str = args.get("path", ".")
            items = await self.async_fs.list_directory(path_str)
            return {"ok": True, "items": items}
        except FileNotFoundError:
            return {"ok": False, "error": "Dir not found"}
        except (PermissionError, FileNotFoundError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

