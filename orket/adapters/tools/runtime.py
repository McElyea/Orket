from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from orket.core.contracts.card_completion_commit import CardWorkspaceMutationAuthority
from orket.logging import log_event


class ToolRuntimeExecutor:
    """Stable runtime seam for invoking mapped tool callables."""

    side_effecting = True

    async def invoke(
        self,
        tool_fn: Callable[..., Any],
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
        tool_name: str | None = None,
        tool_timeout_seconds: float = 60.0,
        workspace: Path | None = None,
        mutation_authority: CardWorkspaceMutationAuthority | None = None,
    ) -> dict[str, Any]:
        resolved_context = dict(context or {})
        try:
            timeout_seconds = max(0.001, float(tool_timeout_seconds))
        except (TypeError, ValueError):
            timeout_seconds = 60.0
        try:
            async def operation():
                return await self._invoke_tool_fn(tool_fn, args, resolved_context)

            if mutation_authority is not None:
                result = await self._invoke_guarded(mutation_authority, operation, timeout_seconds)
            else:
                result = await asyncio.wait_for(operation(), timeout=timeout_seconds)
            if isinstance(result, dict):
                return result
            return {"ok": True, "result": result}
        except TimeoutError:
            resolved_tool_name = str(
                tool_name or resolved_context.get("tool_name") or getattr(tool_fn, "__name__", "unknown")
            )
            log_event(
                "tool_timeout",
                {"tool": resolved_tool_name, "timeout_seconds": timeout_seconds, "ok": False, "error": "tool_timeout"},
                workspace,
            )
            return {"ok": False, "error": "tool_timeout", "tool": resolved_tool_name}
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    async def _invoke_guarded(
        self, authority: CardWorkspaceMutationAuthority, operation: Callable[[], Awaitable[Any]], timeout_seconds: float,
    ) -> Any:
        task = asyncio.create_task(authority.run(operation))
        joined = asyncio.gather(task, return_exceptions=True)
        try:
            result, = await asyncio.wait_for(asyncio.shield(joined), timeout=timeout_seconds)
        except (TimeoutError, asyncio.CancelledError) as exc:
            cancelled = isinstance(exc, asyncio.CancelledError)
            task.cancel()
            # Python 3.11 wait_for can stop waiting on repeated caller cancellation.
            # Retain the application owner's join until its guarded write has drained.
            while True:
                try:
                    await asyncio.shield(joined)
                    break
                except asyncio.CancelledError:
                    cancelled = True
            if cancelled:
                raise asyncio.CancelledError from None
            raise
        if isinstance(result, BaseException):
            raise result
        return result

    async def _invoke_tool_fn(
        self,
        tool_fn: Callable[..., Any],
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        if inspect.iscoroutinefunction(tool_fn):
            return await tool_fn(args, context=context)
        return await asyncio.to_thread(tool_fn, args, context=context)
