from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


class ToolRuntimeExecutor:
    """Stable runtime seam for invoking mapped tool callables."""

    async def invoke(
        self,
        tool_fn: Callable[..., Any],
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_context = dict(context or {})
        try:
            if inspect.iscoroutinefunction(tool_fn):
                result = await tool_fn(args, context=resolved_context)
            else:
                result = tool_fn(args, context=resolved_context)
            if isinstance(result, dict):
                return result
            return {"ok": True, "result": result}
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
