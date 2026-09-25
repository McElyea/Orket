from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

from orket.core.contracts.protocol_hashing import ProtocolCanonicalizationError, hash_canonical_json
from orket.logging import log_event


@dataclass
class MiddlewareOutcome:
    """Optional control surface returned by lifecycle interceptors."""

    short_circuit: bool = False
    reason: str | None = None
    replacement: Any = None


class CachedResultMiddlewareAuthorityError(ValueError):
    """Cached result or call arguments changed after authoritative replay selection."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"E_CACHED_RESULT_MIDDLEWARE_AUTHORITY:{reason}: {detail}")


def _canonical_digest(value: Any, *, reason: str, field: str) -> str:
    try:
        return hash_canonical_json(value)
    except ProtocolCanonicalizationError as exc:
        raise CachedResultMiddlewareAuthorityError(
            reason, f"cached after_tool {field} is not canonical JSON",
        ) from exc


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
        replayed: bool,
        issue: Any,
        role_name: str,
        context: dict[str, Any],
    ) -> Any:
        authoritative_args: dict[str, Any] | None = None
        authoritative_result: Any = None
        hook_args = args
        current = result
        if replayed:
            authoritative_args, authoritative_result = deepcopy((args, result))
            hook_args, current = deepcopy((authoritative_args, authoritative_result))
        for registration in self._iter():
            interceptor = registration.interceptor
            handler = getattr(interceptor, "after_tool", None)
            if not callable(handler):
                continue
            try:
                outcome = handler(
                    tool_name,
                    hook_args,
                    current,
                    issue=issue,
                    role_name=role_name,
                    context=context,
                )
            except Exception as exc:
                self._record_interceptor_error(hook="after_tool", interceptor=interceptor, exc=exc)
                if registration.kind is InterceptorKind.MANDATORY:
                    current = {"ok": False, "error": "interceptor_crash"}
                    break
                continue
            if outcome and outcome.replacement is not None:
                current = outcome.replacement
        if not replayed:
            return current
        assert authoritative_args is not None
        if _canonical_digest(hook_args, reason="args_changed", field="arguments") != _canonical_digest(
            authoritative_args, reason="args_changed", field="authoritative arguments",
        ):
            raise CachedResultMiddlewareAuthorityError(
                "args_changed", "after_tool middleware changed cached call arguments",
            )
        if not isinstance(current, dict):
            raise CachedResultMiddlewareAuthorityError(
                "result_changed",
                f"after_tool middleware replaced cached result with {type(current).__name__}",
            )
        if _canonical_digest(current, reason="result_changed", field="result") != _canonical_digest(
            authoritative_result, reason="result_changed", field="authoritative result",
        ):
            raise CachedResultMiddlewareAuthorityError(
                "result_changed", "after_tool middleware changed cached result",
            )
        return authoritative_result

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
