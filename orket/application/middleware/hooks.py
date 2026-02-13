from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class MiddlewareOutcome:
    """Optional control surface returned by middleware hooks."""

    short_circuit: bool = False
    reason: Optional[str] = None
    replacement: Any = None


class TurnMiddleware(Protocol):
    def before_prompt(
        self,
        messages: List[Dict[str, str]],
        *,
        issue: Any,
        role: Any,
        context: Dict[str, Any],
    ) -> MiddlewareOutcome | None:
        ...

    def after_model(
        self,
        response: Any,
        *,
        issue: Any,
        role: Any,
        context: Dict[str, Any],
    ) -> MiddlewareOutcome | None:
        ...

    def before_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        *,
        issue: Any,
        role_name: str,
        context: Dict[str, Any],
    ) -> MiddlewareOutcome | None:
        ...

    def after_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        *,
        issue: Any,
        role_name: str,
        context: Dict[str, Any],
    ) -> MiddlewareOutcome | None:
        ...

    def on_turn_failure(
        self,
        error: Exception,
        *,
        issue: Any,
        role: Any,
        context: Dict[str, Any],
    ) -> None:
        ...


class MiddlewarePipeline:
    def __init__(self, middlewares: Optional[List[TurnMiddleware]] = None):
        self.middlewares = list(middlewares or [])

    def _iter(self):
        for middleware in self.middlewares:
            yield middleware

    def apply_before_prompt(
        self,
        messages: List[Dict[str, str]],
        *,
        issue: Any,
        role: Any,
        context: Dict[str, Any],
    ) -> tuple[List[Dict[str, str]], Optional[MiddlewareOutcome]]:
        current = messages
        for middleware in self._iter():
            handler = getattr(middleware, "before_prompt", None)
            if not callable(handler):
                continue
            outcome = handler(current, issue=issue, role=role, context=context)
            if not outcome:
                continue
            if outcome.short_circuit:
                return current, outcome
            if outcome.replacement is not None:
                current = outcome.replacement
        return current, None

    def apply_after_model(
        self,
        response: Any,
        *,
        issue: Any,
        role: Any,
        context: Dict[str, Any],
    ) -> tuple[Any, Optional[MiddlewareOutcome]]:
        current = response
        for middleware in self._iter():
            handler = getattr(middleware, "after_model", None)
            if not callable(handler):
                continue
            outcome = handler(current, issue=issue, role=role, context=context)
            if not outcome:
                continue
            if outcome.short_circuit:
                return current, outcome
            if outcome.replacement is not None:
                current = outcome.replacement
        return current, None

    def apply_before_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        *,
        issue: Any,
        role_name: str,
        context: Dict[str, Any],
    ) -> Optional[MiddlewareOutcome]:
        for middleware in self._iter():
            handler = getattr(middleware, "before_tool", None)
            if not callable(handler):
                continue
            outcome = handler(tool_name, args, issue=issue, role_name=role_name, context=context)
            if outcome:
                return outcome
        return None

    def apply_after_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        *,
        issue: Any,
        role_name: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        current = result
        for middleware in self._iter():
            handler = getattr(middleware, "after_tool", None)
            if not callable(handler):
                continue
            outcome = handler(tool_name, args, current, issue=issue, role_name=role_name, context=context)
            if outcome and outcome.replacement is not None:
                current = outcome.replacement
        return current

    def apply_on_turn_failure(
        self,
        error: Exception,
        *,
        issue: Any,
        role: Any,
        context: Dict[str, Any],
    ) -> None:
        for middleware in self._iter():
            handler = getattr(middleware, "on_turn_failure", None)
            if callable(handler):
                handler(error, issue=issue, role=role, context=context)
