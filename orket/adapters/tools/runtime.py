from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Optional


class ToolRuntimeExecutor:
    """Stable runtime seam for invoking mapped tool callables."""

    async def invoke(
        self,
        tool_fn: Callable,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        resolved_context = dict(context or {})
        try:
            if inspect.iscoroutinefunction(tool_fn):
                return await tool_fn(args, context=resolved_context)
            return tool_fn(args, context=resolved_context)
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
