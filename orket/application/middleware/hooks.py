from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class MiddlewareOutcome:
    """Optional control surface returned by lifecycle interceptors."""

    short_circuit: bool = False
    reason: str | None = None
    replacement: Any = None


class TurnLifecycleInterceptor(Protocol):
    def before_prompt(
        self,
        messages: list[dict[str, str]],
        *,
        issue: Any,
        role: Any,
        context: dict[str, Any],
    ) -> MiddlewareOutcome | None: ...

    def after_model(
        self,
        response: Any,
        *,
        issue: Any,
        role: Any,
        context: dict[str, Any],
    ) -> MiddlewareOutcome | None: ...

    def before_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        *,
        issue: Any,
        role_name: str,
        context: dict[str, Any],
    ) -> MiddlewareOutcome | None: ...

    def after_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        *,
        issue: Any,
        role_name: str,
        context: dict[str, Any],
    ) -> MiddlewareOutcome | None: ...

    def on_turn_failure(
        self,
        error: Exception,
        *,
        issue: Any,
        role: Any,
        context: dict[str, Any],
    ) -> None: ...


class TurnLifecycleInterceptors:
    def __init__(
        self,
        interceptors: list[TurnLifecycleInterceptor] | None = None,
        *,
        middlewares: list[TurnLifecycleInterceptor] | None = None,
    ):
        # Backward compatibility: `middlewares=` was the old constructor argument.
        source = interceptors if interceptors is not None else middlewares
        self.interceptors = list(source or [])

    def _iter(self):
        yield from self.interceptors

    def apply_before_prompt(
        self,
        messages: list[dict[str, str]],
        *,
        issue: Any,
        role: Any,
        context: dict[str, Any],
    ) -> tuple[list[dict[str, str]], MiddlewareOutcome | None]:
        current = messages
        for interceptor in self._iter():
            handler = getattr(interceptor, "before_prompt", None)
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
        context: dict[str, Any],
    ) -> tuple[Any, MiddlewareOutcome | None]:
        current = response
        for interceptor in self._iter():
            handler = getattr(interceptor, "after_model", None)
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
        args: dict[str, Any],
        *,
        issue: Any,
        role_name: str,
        context: dict[str, Any],
    ) -> MiddlewareOutcome | None:
        for interceptor in self._iter():
            handler = getattr(interceptor, "before_tool", None)
            if not callable(handler):
                continue
            outcome = handler(tool_name, args, issue=issue, role_name=role_name, context=context)
            if outcome:
                return outcome
        return None

    def apply_after_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        *,
        issue: Any,
        role_name: str,
        context: dict[str, Any],
    ) -> Any:
        current = result
        for interceptor in self._iter():
            handler = getattr(interceptor, "after_tool", None)
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
        context: dict[str, Any],
    ) -> None:
        for interceptor in self._iter():
            handler = getattr(interceptor, "on_turn_failure", None)
            if callable(handler):
                handler(error, issue=issue, role=role, context=context)


# Backward-compatible aliases.
TurnMiddleware = TurnLifecycleInterceptor
MiddlewarePipeline = TurnLifecycleInterceptors
