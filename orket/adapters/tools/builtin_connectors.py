from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.bound_filesystem import BOUND_FILESYSTEM_TOOLS, BoundFilesystemExecutor
from orket.adapters.tools.families.filesystem import FileSystemTools
from orket.core.contracts.owned_command import CommandExecutionUncertain, CommandRunner
from orket.core.contracts.provider_http import HttpRequestPort
from orket.core.domain.outward_authorization import OutwardAuthorization

BUILTIN_CONNECTOR_SIDE_EFFECTS: dict[str, bool] = {
    "read_file": False,
    "write_file": True,
    "create_directory": True,
    "delete_file": True,
    "run_command": True,
    "http_get": True,
    "http_post": True,
}


side_effecting = True


class BuiltInConnectorExecutionError(RuntimeError):
    pass


class BuiltInConnectorExecutor:
    side_effecting_connectors = frozenset(name for name, side_effecting in BUILTIN_CONNECTOR_SIDE_EFFECTS.items() if side_effecting)

    def __init__(
        self,
        *,
        workspace_root: Path,
        command_runner: CommandRunner,
        http_requester: HttpRequestPort,
        http_allowlist: tuple[str, ...] = (),
    ) -> None:
        self.workspace_root = workspace_root
        self.command_runner = command_runner
        self.http_requester = http_requester
        self.file_tools = FileSystemTools(workspace_root, references=[])
        self.bound_filesystem = BoundFilesystemExecutor()
        self.http_allowlist = tuple(host.strip().lower() for host in http_allowlist if host.strip())

    async def invoke(
        self, connector_name: str, args: dict[str, Any], *, timeout_seconds: float,
        authorization: OutwardAuthorization | None = None,
    ) -> dict[str, Any]:
        name = str(connector_name or "").strip()
        if authorization is not None and name in BOUND_FILESYSTEM_TOOLS:
            if name != authorization.tool:
                raise RuntimeError("E_OUTWARD_AUTHORIZATION_ARGUMENT_DRIFT")
            return await self.bound_filesystem.invoke(authorization, args)
        if name in BOUND_FILESYSTEM_TOOLS:
            return await run_owned_io(lambda: self._invoke_filesystem(name, args), label=name)
        if name == "run_command":
            return await self._run_command(args, timeout_seconds=timeout_seconds)
        if name == "http_get":
            return await self._http_get(args, timeout_seconds=timeout_seconds)
        if name == "http_post":
            return await self._http_post(args, timeout_seconds=timeout_seconds)
        raise BuiltInConnectorExecutionError(f"unsupported built-in connector: {connector_name}")

    async def _invoke_filesystem(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "read_file":
            return await self.file_tools.read_file(args)
        if name == "write_file":
            return await self.file_tools.write_file(args)
        if name == "create_directory":
            return await self.file_tools.create_directory(args)
        if name == "delete_file":
            return await self._delete_file(args)
        raise BuiltInConnectorExecutionError(f"unsupported filesystem connector: {name}")

    async def _delete_file(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            path_str = FileSystemTools._require_path_arg(args)
            captured = self.file_tools.async_fs.capture()

            def delete():
                resolved = captured._resolve_safe_path(path_str, write=True)
                if not resolved.exists():
                    return {"ok": False, "error": "File not found"}
                if resolved.is_dir():
                    return {"ok": False, "error": "delete_file only deletes files"}
                resolved.unlink()
                return {"ok": True, "path": str(resolved)}

            return await run_owned_thread(delete, label="connector-delete")
        except (PermissionError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def _run_command(self, args: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        try:
            argv = _argv_from_command(args.get("command"))
        except (ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}
        result = await self.command_runner.run(
            argv, cwd=self.workspace_root, timeout_seconds=timeout_seconds,
        )
        if (not result.cleanup_confirmed or result.reason in {"cleanup_unconfirmed", "capture_incomplete", "cancelled"}
                or (result.reason == "completed" and not result.capture_complete)):
            raise CommandExecutionUncertain(result)
        stdout_text = result.stdout.decode("utf-8", errors="replace")
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        payload = {
            "ok": result.reason == "completed" and result.returncode == 0,
            "returncode": result.returncode,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
            "stdout_preview": stdout_text[:256],
            "stderr_preview": stderr_text[:256],
            "process_lifetime": result.lifetime(),
        }
        if result.reason != "completed":
            payload["error"] = result.reason
        if result.reason == "timeout":
            payload["timeout_seconds"] = timeout_seconds
        return payload

    async def _http_get(self, args: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        try:
            url = _require_url(args)
            self._require_allowlisted_url(url)
            response = await self.http_requester.request("GET", url, timeout_s=timeout_seconds)
            return _http_result(response)
        except (httpx.HTTPError, PermissionError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def _http_post(self, args: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        try:
            url = _require_url(args)
            self._require_allowlisted_url(url)
            body = args.get("body")
            response = await self.http_requester.request("POST", url, timeout_s=timeout_seconds,
                json=body if isinstance(body, dict) else None, content=body if isinstance(body, str) else None)
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
