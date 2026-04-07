from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

from orket.logging import log_event


@dataclass
class MiddlewareOutcome:
    """Optional control surface returned by lifecycle interceptors."""

    short_circuit: bool = False
    reason: str | None = None
    replacement: Any = None


class InterceptorKind(StrEnum):
    ADVISORY = "advisory"
    MANDATORY = "mandatory"


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


@dataclass(frozen=True)
class TurnLifecycleInterceptorRegistration:
    interceptor: TurnLifecycleInterceptor
    kind: InterceptorKind = InterceptorKind.ADVISORY

    def __post_init__(self) -> None:
        if not isinstance(self.kind, InterceptorKind):
            object.__setattr__(self, "kind", InterceptorKind(str(self.kind)))


InterceptorRegistrationInput = TurnLifecycleInterceptor | TurnLifecycleInterceptorRegistration


class TurnLifecycleInterceptors:
    def __init__(
        self,
        interceptors: list[InterceptorRegistrationInput] | None = None,
        *,
        middlewares: list[InterceptorRegistrationInput] | None = None,
        workspace: Path | None = None,
    ) -> None:
        # Backward compatibility: `middlewares=` was the old constructor argument.
        source = interceptors if interceptors is not None else middlewares
        self._registrations: list[TurnLifecycleInterceptorRegistration] = [
            self._normalize_registration(item) for item in list(source or [])
        ]
        self.interceptors: list[TurnLifecycleInterceptor] = [
            registration.interceptor for registration in self._registrations
        ]
        self.workspace = workspace

    def _normalize_registration(
        self,
        item: InterceptorRegistrationInput,
    ) -> TurnLifecycleInterceptorRegistration:
        if isinstance(item, TurnLifecycleInterceptorRegistration):
            return item
        return TurnLifecycleInterceptorRegistration(interceptor=item)

    def _iter(self) -> Iterator[TurnLifecycleInterceptorRegistration]:
        yield from self._registrations

    def register(
        self,
        interceptor: TurnLifecycleInterceptor,
        *,
        kind: InterceptorKind = InterceptorKind.ADVISORY,
    ) -> None:
        registration = TurnLifecycleInterceptorRegistration(interceptor=interceptor, kind=kind)
        self._registrations.append(registration)
        self.interceptors.append(interceptor)

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

    def _mandatory_crash_outcome(self) -> MiddlewareOutcome:
        return MiddlewareOutcome(short_circuit=True, reason="interceptor_crash")

    def apply_before_prompt(
        self,
        messages: list[dict[str, str]],
        *,
        issue: Any,
        role: Any,
        context: dict[str, Any],
    ) -> tuple[list[dict[str, str]], MiddlewareOutcome | None]:
        current = messages
        for registration in self._iter():
            interceptor = registration.interceptor
            handler = getattr(interceptor, "before_prompt", None)
            if not callable(handler):
                continue
            try:
                outcome = handler(current, issue=issue, role=role, context=context)
            except Exception as exc:
                self._record_interceptor_error(hook="before_prompt", interceptor=interceptor, exc=exc)
                if registration.kind is InterceptorKind.MANDATORY:
                    return current, self._mandatory_crash_outcome()
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
        for registration in self._iter():
            interceptor = registration.interceptor
            handler = getattr(interceptor, "after_model", None)
            if not callable(handler):
                continue
            try:
                outcome = handler(current, issue=issue, role=role, context=context)
            except Exception as exc:
                self._record_interceptor_error(hook="after_model", interceptor=interceptor, exc=exc)
                if registration.kind is InterceptorKind.MANDATORY:
                    return current, self._mandatory_crash_outcome()
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
        for registration in self._iter():
            interceptor = registration.interceptor
            handler = getattr(interceptor, "before_tool", None)
            if not callable(handler):
                continue
            try:
                outcome = handler(tool_name, args, issue=issue, role_name=role_name, context=context)
            except Exception as exc:
                self._record_interceptor_error(hook="before_tool", interceptor=interceptor, exc=exc)
                if registration.kind is InterceptorKind.MANDATORY:
                    return self._mandatory_crash_outcome()
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
        for registration in self._iter():
            interceptor = registration.interceptor
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
                if registration.kind is InterceptorKind.MANDATORY:
                    return {"ok": False, "error": "interceptor_crash"}
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
        for registration in self._iter():
            interceptor = registration.interceptor
            handler = getattr(interceptor, "on_turn_failure", None)
            if not callable(handler):
                continue
            try:
                handler(error, issue=issue, role=role, context=context)
            except Exception as exc:
                self._record_interceptor_error(hook="on_turn_failure", interceptor=interceptor, exc=exc)
                if registration.kind is InterceptorKind.MANDATORY:
                    break


# Backward-compatible aliases.
TurnMiddleware = TurnLifecycleInterceptor
MiddlewarePipeline = TurnLifecycleInterceptors
