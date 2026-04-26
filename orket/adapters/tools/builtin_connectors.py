from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from orket.adapters.tools.families.filesystem import FileSystemTools

BUILTIN_CONNECTOR_SIDE_EFFECTS: dict[str, bool] = {
    "read_file": False,
    "write_file": True,
    "create_directory": True,
    "delete_file": True,
    "run_command": True,
    "http_get": True,
    "http_post": True,
}


class BuiltInConnectorExecutionError(RuntimeError):
    pass


class BuiltInConnectorExecutor:
    side_effecting_connectors = frozenset(name for name, side_effecting in BUILTIN_CONNECTOR_SIDE_EFFECTS.items() if side_effecting)

    def __init__(
        self,
        *,
        workspace_root: Path,
        http_allowlist: tuple[str, ...] = (),
    ) -> None:
        self.workspace_root = workspace_root
        self.file_tools = FileSystemTools(workspace_root, references=[])
        self.http_allowlist = tuple(host.strip().lower() for host in http_allowlist if host.strip())

    async def invoke(self, connector_name: str, args: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        name = str(connector_name or "").strip()
        if name == "read_file":
            return await self.file_tools.read_file(args)
        if name == "write_file":
            return await self.file_tools.write_file(args)
        if name == "create_directory":
            return await self.file_tools.create_directory(args)
        if name == "delete_file":
            return await self._delete_file(args)
        if name == "run_command":
            return await self._run_command(args)
        if name == "http_get":
            return await self._http_get(args, timeout_seconds=timeout_seconds)
        if name == "http_post":
            return await self._http_post(args, timeout_seconds=timeout_seconds)
        raise BuiltInConnectorExecutionError(f"unsupported built-in connector: {connector_name}")

    async def _delete_file(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            path_str = FileSystemTools._require_path_arg(args)
            resolved = self.file_tools.async_fs._resolve_safe_path(path_str, write=True)
            if not await asyncio.to_thread(resolved.exists):
                return {"ok": False, "error": "File not found"}
            if await asyncio.to_thread(resolved.is_dir):
                return {"ok": False, "error": "delete_file only deletes files"}
            await asyncio.to_thread(resolved.unlink)
            return {"ok": True, "path": str(resolved)}
        except (PermissionError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def _run_command(self, args: dict[str, Any]) -> dict[str, Any]:
        process: asyncio.subprocess.Process | None = None
        try:
            argv = _argv_from_command(args.get("command"))
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(self.workspace_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            return {
                "ok": process.returncode == 0,
                "returncode": process.returncode,
                "stdout_bytes": len(stdout_text.encode("utf-8")),
                "stderr_bytes": len(stderr_text.encode("utf-8")),
                "stdout_preview": stdout_text[:256],
                "stderr_preview": stderr_text[:256],
            }
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            raise
        except (OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def _http_get(self, args: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        try:
            url = _require_url(args)
            self._require_allowlisted_url(url)
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(url)
            return _http_result(response)
        except (httpx.HTTPError, PermissionError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def _http_post(self, args: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        try:
            url = _require_url(args)
            self._require_allowlisted_url(url)
            body = args.get("body")
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, json=body if isinstance(body, dict) else None, content=body if isinstance(body, str) else None)
            return _http_result(response)
        except (httpx.HTTPError, PermissionError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    def _require_allowlisted_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("url must be an absolute http or https URL")
        if not self.http_allowlist:
            raise PermissionError("HTTP connector allowlist is required")
        host = parsed.hostname.lower()
        if host not in self.http_allowlist:
            raise PermissionError(f"HTTP host is not allowlisted: {host}")


def _argv_from_command(command: Any) -> list[str]:
    if isinstance(command, str):
        argv = shlex.split(command, posix=True)
    elif isinstance(command, list) and all(isinstance(item, str) for item in command):
        argv = list(command)
    else:
        raise TypeError("command must be a string or string array")
    if not argv:
        raise ValueError("command is required")
    if any("\x00" in item for item in argv):
        raise ValueError("command arguments must not contain NUL bytes")
    return argv


def _require_url(args: dict[str, Any]) -> str:
    url = args.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url is required")
    return url


def _http_result(response: httpx.Response) -> dict[str, Any]:
    body = response.text
    return {
        "ok": 200 <= response.status_code < 400,
        "status_code": response.status_code,
        "body_bytes": len(body.encode("utf-8")),
    }


__all__ = [
    "BUILTIN_CONNECTOR_SIDE_EFFECTS",
    "BuiltInConnectorExecutionError",
    "BuiltInConnectorExecutor",
]
