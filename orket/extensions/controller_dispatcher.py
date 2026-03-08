from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket_extension_sdk.controller import (
    ControllerChildCall,
    ControllerChildResult,
    ControllerPolicyCaps,
    ControllerRunEnvelope,
    ControllerRunSummary,
)

from .manager import ExtensionManager
from .models import CONTRACT_STYLE_SDK_V0
from .controller_dispatcher_contract import (
    DEFAULT_CHILD_TIMEOUT_SECONDS,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_FANOUT,
    ERROR_CHILD_EXECUTION_FAILED,
    ERROR_CHILD_SDK_REQUIRED,
    ERROR_CHILD_TIMEOUT_INVALID,
    ERROR_CYCLE_DENIED,
    ERROR_ENVELOPE_INVALID,
    ERROR_MAX_DEPTH_EXCEEDED,
    ERROR_MAX_FANOUT_EXCEEDED,
    ERROR_RECURSION_DENIED,
    failed_child_result,
    failed_summary,
    normalize_controller_error,
    not_attempted_results,
)


@dataclass(frozen=True)
class _ResolvedCaps:
    requested: ControllerPolicyCaps
    enforced: ControllerPolicyCaps


@dataclass(frozen=True)
class _ChildOutcome:
    result: ControllerChildResult
    error_code: str | None


class ControllerDispatcher:
    """Sequential controller dispatcher using ExtensionManager as the only child authority."""

    def __init__(
        self,
        *,
        extension_manager: ExtensionManager | None = None,
        runtime_policy_caps: ControllerPolicyCaps | None = None,
    ) -> None:
        self._extension_manager = extension_manager or ExtensionManager()
        self._runtime_policy_caps = self._resolve_runtime_policy_caps(runtime_policy_caps)

    async def dispatch(
        self,
        *,
        payload: dict[str, Any],
        workspace: Path,
        department: str,
    ) -> ControllerRunSummary:
        envelope, envelope_error = self._parse_envelope(payload)
        if envelope is None:
            return failed_summary(
                controller_workload_id=str((payload or {}).get("controller_workload_id") or "controller"),
                error_code=envelope_error or ERROR_ENVELOPE_INVALID,
                child_results=[],
            )
        return await self._dispatch_envelope(
            envelope=envelope,
            workspace=workspace,
            department=str(department or "core").strip() or "core",
        )

    async def _dispatch_envelope(
        self,
        *,
        envelope: ControllerRunEnvelope,
        workspace: Path,
        department: str,
    ) -> ControllerRunSummary:
        caps = self._resolve_caps(envelope.requested_caps)
        controller_id = envelope.controller_workload_id

        if len(envelope.children) > int(caps.enforced.max_fanout or DEFAULT_MAX_FANOUT):
            return failed_summary(
                controller_workload_id=controller_id,
                error_code=ERROR_MAX_FANOUT_EXCEEDED,
                child_results=[],
                requested_caps=caps.requested,
                enforced_caps=caps.enforced,
            )

        next_depth = envelope.parent_depth + 1
        if next_depth > int(caps.enforced.max_depth or DEFAULT_MAX_DEPTH):
            return failed_summary(
                controller_workload_id=controller_id,
                error_code=ERROR_MAX_DEPTH_EXCEEDED,
                child_results=[],
                requested_caps=caps.requested,
                enforced_caps=caps.enforced,
            )

        ancestry = list(envelope.ancestry)
        if ancestry and ancestry[-1] == controller_id:
            return failed_summary(
                controller_workload_id=controller_id,
                error_code=ERROR_RECURSION_DENIED,
                child_results=[],
                requested_caps=caps.requested,
                enforced_caps=caps.enforced,
            )
        if controller_id in ancestry:
            return failed_summary(
                controller_workload_id=controller_id,
                error_code=ERROR_CYCLE_DENIED,
                child_results=[],
                requested_caps=caps.requested,
                enforced_caps=caps.enforced,
            )

        active_ancestry = [*ancestry, controller_id]
        child_results: list[ControllerChildResult] = []
        for index, child in enumerate(envelope.children):
            outcome = await self._run_child(
                child=child,
                controller_workload_id=controller_id,
                active_ancestry=active_ancestry,
                caps=caps,
                next_depth=next_depth,
                workspace=workspace,
                department=department,
            )
            child_results.append(outcome.result)
            if outcome.error_code is None:
                continue
            child_results.extend(
                not_attempted_results(
                    children=envelope.children[index + 1 :],
                    requested_timeout=caps.requested.child_timeout_seconds,
                    enforced_timeout=caps.enforced.child_timeout_seconds,
                    requested_caps=caps.requested,
                    enforced_caps=caps.enforced,
                )
            )
            return failed_summary(
                controller_workload_id=controller_id,
                error_code=outcome.error_code,
                child_results=child_results,
                requested_caps=caps.requested,
                enforced_caps=caps.enforced,
            )

        return ControllerRunSummary(
            controller_workload_id=controller_id,
            status="success",
            requested_caps=caps.requested,
            enforced_caps=caps.enforced,
            child_results=child_results,
            error_code=None,
            metadata={"parent_depth": envelope.parent_depth, "next_depth": next_depth, "ancestry": active_ancestry},
        )

    async def _run_child(
        self,
        *,
        child: ControllerChildCall,
        controller_workload_id: str,
        active_ancestry: list[str],
        caps: _ResolvedCaps,
        next_depth: int,
        workspace: Path,
        department: str,
    ) -> _ChildOutcome:
        requested_timeout = self._requested_timeout(caps.requested, child)
        enforced_timeout = self._enforced_timeout(caps.enforced, requested_timeout)

        guard_error = self._guard_child(
            child=child,
            controller_workload_id=controller_workload_id,
            active_ancestry=active_ancestry,
        )
        if guard_error is not None:
            return _ChildOutcome(
                result=failed_child_result(
                    child=child,
                    error_code=guard_error,
                    requested_timeout=requested_timeout,
                    enforced_timeout=enforced_timeout,
                    requested_caps=caps.requested,
                    enforced_caps=caps.enforced,
                ),
                error_code=guard_error,
            )

        resolved = self._extension_manager.resolve_workload(child.target_workload)
        if resolved is None:
            return _ChildOutcome(
                result=failed_child_result(
                    child=child,
                    error_code=ERROR_CHILD_EXECUTION_FAILED,
                    requested_timeout=requested_timeout,
                    enforced_timeout=enforced_timeout,
                    requested_caps=caps.requested,
                    enforced_caps=caps.enforced,
                ),
                error_code=ERROR_CHILD_EXECUTION_FAILED,
            )
        extension_record, workload_record = resolved
        if workload_record.contract_style != CONTRACT_STYLE_SDK_V0 and extension_record.contract_style != CONTRACT_STYLE_SDK_V0:
            return _ChildOutcome(
                result=failed_child_result(
                    child=child,
                    error_code=ERROR_CHILD_SDK_REQUIRED,
                    requested_timeout=requested_timeout,
                    enforced_timeout=enforced_timeout,
                    requested_caps=caps.requested,
                    enforced_caps=caps.enforced,
                ),
                error_code=ERROR_CHILD_SDK_REQUIRED,
            )

        child_input = dict(child.payload)
        child_input.setdefault("parent_depth", next_depth)
        child_input.setdefault("ancestry", list(active_ancestry))

        try:
            run_call = self._extension_manager.run_workload(
                workload_id=child.target_workload,
                input_config=child_input,
                workspace=workspace,
                department=department,
            )
            run_result = await run_call if enforced_timeout is None else await asyncio.wait_for(
                run_call, timeout=float(enforced_timeout)
            )
        except asyncio.TimeoutError:
            return _ChildOutcome(
                result=failed_child_result(
                    child=child,
                    error_code=ERROR_CHILD_EXECUTION_FAILED,
                    requested_timeout=requested_timeout,
                    enforced_timeout=enforced_timeout,
                    requested_caps=caps.requested,
                    enforced_caps=caps.enforced,
                ),
                error_code=ERROR_CHILD_EXECUTION_FAILED,
            )
        except (RuntimeError, TypeError, ValueError) as exc:
            error_code = normalize_controller_error(str(exc))
            return _ChildOutcome(
                result=failed_child_result(
                    child=child,
                    error_code=error_code,
                    requested_timeout=requested_timeout,
                    enforced_timeout=enforced_timeout,
                    requested_caps=caps.requested,
                    enforced_caps=caps.enforced,
                ),
                error_code=error_code,
            )

        run_summary = dict(run_result.summary or {})
        child_ok = bool(run_summary.get("ok", True))
        if child_ok:
            return _ChildOutcome(
                result=ControllerChildResult(
                    target_workload=child.target_workload,
                    status="success",
                    requested_timeout=requested_timeout,
                    enforced_timeout=enforced_timeout,
                    requested_caps=caps.requested,
                    enforced_caps=caps.enforced,
                    artifact_refs=[
                        {"kind": "artifact_root", "path": str(run_result.artifact_root)},
                        {"kind": "provenance", "path": str(run_result.provenance_path)},
                    ],
                    normalized_error=None,
                    summary=run_summary,
                ),
                error_code=None,
            )

        return _ChildOutcome(
            result=failed_child_result(
                child=child,
                error_code=ERROR_CHILD_EXECUTION_FAILED,
                requested_timeout=requested_timeout,
                enforced_timeout=enforced_timeout,
                requested_caps=caps.requested,
                enforced_caps=caps.enforced,
                summary=run_summary,
                artifact_refs=[
                    {"kind": "artifact_root", "path": str(run_result.artifact_root)},
                    {"kind": "provenance", "path": str(run_result.provenance_path)},
                ],
            ),
            error_code=ERROR_CHILD_EXECUTION_FAILED,
        )

    @staticmethod
    def _resolve_runtime_policy_caps(runtime_policy_caps: ControllerPolicyCaps | None) -> ControllerPolicyCaps:
        base = runtime_policy_caps or ControllerPolicyCaps(
            max_depth=DEFAULT_MAX_DEPTH,
            max_fanout=DEFAULT_MAX_FANOUT,
            child_timeout_seconds=DEFAULT_CHILD_TIMEOUT_SECONDS,
        )
        return ControllerPolicyCaps(
            max_depth=ControllerDispatcher._read_env_int(
                "ORKET_CONTROLLER_MAX_DEPTH", fallback=int(base.max_depth or DEFAULT_MAX_DEPTH), minimum=0
            ),
            max_fanout=ControllerDispatcher._read_env_int(
                "ORKET_CONTROLLER_MAX_FANOUT", fallback=int(base.max_fanout or DEFAULT_MAX_FANOUT), minimum=1
            ),
            child_timeout_seconds=ControllerDispatcher._read_env_int(
                "ORKET_CONTROLLER_CHILD_TIMEOUT_SECONDS",
                fallback=int(base.child_timeout_seconds or DEFAULT_CHILD_TIMEOUT_SECONDS),
                minimum=1,
            ),
        )

    @staticmethod
    def _read_env_int(name: str, *, fallback: int, minimum: int) -> int:
        raw = str(os.getenv(name, "")).strip()
        if not raw:
            return fallback
        parsed = int(raw)
        if parsed < minimum:
            raise ValueError(ERROR_ENVELOPE_INVALID)
        return parsed

    def _resolve_caps(self, requested_caps: ControllerPolicyCaps | None) -> _ResolvedCaps:
        policy = self._runtime_policy_caps
        requested = requested_caps or ControllerPolicyCaps()
        requested_resolved = ControllerPolicyCaps(
            max_depth=int(requested.max_depth if requested.max_depth is not None else policy.max_depth or DEFAULT_MAX_DEPTH),
            max_fanout=int(
                requested.max_fanout if requested.max_fanout is not None else policy.max_fanout or DEFAULT_MAX_FANOUT
            ),
            child_timeout_seconds=int(
                requested.child_timeout_seconds
                if requested.child_timeout_seconds is not None
                else policy.child_timeout_seconds or DEFAULT_CHILD_TIMEOUT_SECONDS
            ),
        )
        enforced = ControllerPolicyCaps(
            max_depth=min(int(requested_resolved.max_depth or DEFAULT_MAX_DEPTH), int(policy.max_depth or DEFAULT_MAX_DEPTH)),
            max_fanout=min(
                int(requested_resolved.max_fanout or DEFAULT_MAX_FANOUT), int(policy.max_fanout or DEFAULT_MAX_FANOUT)
            ),
            child_timeout_seconds=min(
                int(requested_resolved.child_timeout_seconds or DEFAULT_CHILD_TIMEOUT_SECONDS),
                int(policy.child_timeout_seconds or DEFAULT_CHILD_TIMEOUT_SECONDS),
            ),
        )
        return _ResolvedCaps(requested=requested_resolved, enforced=enforced)

    @staticmethod
    def _parse_envelope(payload: dict[str, Any]) -> tuple[ControllerRunEnvelope | None, str | None]:
        if not isinstance(payload, dict):
            return None, ERROR_ENVELOPE_INVALID
        try:
            return ControllerRunEnvelope.model_validate(payload), None
        except Exception as exc:
            text = str(exc)
            if ERROR_CHILD_TIMEOUT_INVALID in text:
                return None, ERROR_CHILD_TIMEOUT_INVALID
            return None, ERROR_ENVELOPE_INVALID

    @staticmethod
    def _guard_child(
        *, child: ControllerChildCall, controller_workload_id: str, active_ancestry: list[str]
    ) -> str | None:
        if child.target_workload == controller_workload_id:
            return ERROR_RECURSION_DENIED
        if child.target_workload in active_ancestry:
            return ERROR_CYCLE_DENIED
        if child.contract_style != CONTRACT_STYLE_SDK_V0:
            return ERROR_CHILD_SDK_REQUIRED
        return None

    @staticmethod
    def _requested_timeout(requested_caps: ControllerPolicyCaps, child: ControllerChildCall) -> int | None:
        if child.timeout_seconds is not None:
            return int(child.timeout_seconds)
        if requested_caps.child_timeout_seconds is not None:
            return int(requested_caps.child_timeout_seconds)
        return None

    @staticmethod
    def _enforced_timeout(enforced_caps: ControllerPolicyCaps, requested_timeout: int | None) -> int | None:
        if requested_timeout is None:
            return int(enforced_caps.child_timeout_seconds) if enforced_caps.child_timeout_seconds is not None else None
        if enforced_caps.child_timeout_seconds is None:
            return int(requested_timeout)
        return min(int(requested_timeout), int(enforced_caps.child_timeout_seconds))


__all__ = [
    "ControllerDispatcher",
    "DEFAULT_CHILD_TIMEOUT_SECONDS",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_FANOUT",
    "ERROR_CHILD_EXECUTION_FAILED",
    "ERROR_CHILD_SDK_REQUIRED",
    "ERROR_CHILD_TIMEOUT_INVALID",
    "ERROR_CYCLE_DENIED",
    "ERROR_ENVELOPE_INVALID",
    "ERROR_MAX_DEPTH_EXCEEDED",
    "ERROR_MAX_FANOUT_EXCEEDED",
    "ERROR_RECURSION_DENIED",
]
