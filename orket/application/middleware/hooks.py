from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from orket.logging import log_event


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
        workspace: Path | None = None,
    ) -> None:
        # Backward compatibility: `middlewares=` was the old constructor argument.
        source = interceptors if interceptors is not None else middlewares
        self.interceptors: list[TurnLifecycleInterceptor] = list(source or [])
        self.workspace = workspace

    def _iter(self) -> Iterator[TurnLifecycleInterceptor]:
        yield from self.interceptors

    def bind_workspace(self, workspace: Path) -> None:
        if self.workspace is None:
            self.workspace = workspace

    def _record_interceptor_error(
        self,
        *,
        hook: str,
        interceptor: TurnLifecycleInterceptor,
        exc: Exception,
    ) -> None:
        log_event(
            "interceptor_error",
            {"hook": hook, "interceptor": type(interceptor).__name__, "error": str(exc)},
            self.workspace,
        )

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
            try:
                outcome = handler(current, issue=issue, role=role, context=context)
            except Exception as exc:
                self._record_interceptor_error(hook="before_prompt", interceptor=interceptor, exc=exc)
                continue
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
            try:
                outcome = handler(current, issue=issue, role=role, context=context)
            except Exception as exc:
                self._record_interceptor_error(hook="after_model", interceptor=interceptor, exc=exc)
                continue
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
            try:
                outcome = handler(tool_name, args, issue=issue, role_name=role_name, context=context)
            except Exception as exc:
                self._record_interceptor_error(hook="before_tool", interceptor=interceptor, exc=exc)
                continue
            if outcome:
                return cast(MiddlewareOutcome, outcome)
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
            try:
                outcome = handler(
                    tool_name,
                    args,
                    current,
                    issue=issue,
                    role_name=role_name,
                    context=context,
                )
            except Exception as exc:
                self._record_interceptor_error(hook="after_tool", interceptor=interceptor, exc=exc)
                continue
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
            if not callable(handler):
                continue
            try:
                handler(error, issue=issue, role=role, context=context)
            except Exception as exc:
                self._record_interceptor_error(hook="on_turn_failure", interceptor=interceptor, exc=exc)


# Backward-compatible aliases.
TurnMiddleware = TurnLifecycleInterceptor
MiddlewarePipeline = TurnLifecycleInterceptors
