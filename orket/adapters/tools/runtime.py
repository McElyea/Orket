from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.core.contracts.card_completion_commit import CardWorkspaceMutationAuthority
from orket.logging import log_event

side_effecting = True


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
        native_failures: list[BaseException] = []
        try:
            timeout_seconds = max(0.001, float(tool_timeout_seconds))
        except (TypeError, ValueError):
            timeout_seconds = 60.0
        try:
            async def operation():
                return await self._invoke_tool_fn(tool_fn, args, resolved_context, native_failures)

            result = await self._invoke_owned(operation, timeout_seconds, native_failures, mutation_authority)
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

    async def _invoke_owned(
        self, operation: Callable[[], Awaitable[Any]], timeout_seconds: float, native_failures: list[BaseException],
        authority: CardWorkspaceMutationAuthority | None,
    ) -> Any:
        authority_failures: list[BaseException] = []

        async def bounded():
            if authority is not None:
                try:
                    candidate = authority.run(operation)
                    if not asyncio.iscoroutine(candidate):
                        raise TypeError("mutation authority must return a coroutine")
                    result = await candidate
                except BaseException as failure:  # Preserve the authority's complete body/cleanup selection.
                    authority_failures.append(failure)
                    raise
                # The existing guarded route treats exception values as failures.
                if isinstance(result, BaseException):
                    raise result
                return (result,)
            # Unguarded tool exception objects remain ordinary return values.
            return (await operation(),)

        try:
            async with asyncio.timeout(timeout_seconds):
                result, = await run_owned_io(bounded, label="tool-invocation",
                                            preserve_failure=True, cancel_on_interrupt=True)
            return result
        except BaseException:  # The shared owner has settled; retain actual native failure precedence.
            if not native_failures:
                raise
            if authority is not None and (not authority_failures or authority_failures[0] is not native_failures[0]):
                raise
            failure = native_failures[0]
        # Raise outside the handler so a deadline wrapper cannot become its context.
        raise failure

    async def _invoke_tool_fn(
        self,
        tool_fn: Callable[..., Any],
        args: dict[str, Any],
        context: dict[str, Any],
        native_failures: list[BaseException],
    ) -> Any:
        if inspect.iscoroutinefunction(tool_fn):
            return await tool_fn(args, context=context)

        def native():
            try:
                return (tool_fn(args, context=context),)
            except BaseException as failure:
                native_failures.append(failure)
                raise

        result, = await run_owned_thread(native, label="tool-synchronous-call")
        return result
