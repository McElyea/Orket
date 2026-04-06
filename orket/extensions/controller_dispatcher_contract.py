from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from orket_extension_sdk.controller import (
    ControllerChildCall,
    ControllerChildResult,
    ControllerPolicyCaps,
    ControllerRunEnvelope,
    ControllerRunStatus,
    ControllerRunSummary,
)

from .models import CONTRACT_STYLE_SDK_V0

DEFAULT_MAX_DEPTH = 1
DEFAULT_MAX_FANOUT = 5
DEFAULT_CHILD_TIMEOUT_SECONDS = 900

ERROR_ENVELOPE_INVALID = "controller.envelope_invalid"
ERROR_CHILD_SDK_REQUIRED = "controller.child_sdk_required"
ERROR_MAX_DEPTH_EXCEEDED = "controller.max_depth_exceeded"
ERROR_MAX_FANOUT_EXCEEDED = "controller.max_fanout_exceeded"
ERROR_CHILD_TIMEOUT_INVALID = "controller.child_timeout_invalid"
ERROR_RECURSION_DENIED = "controller.recursion_denied"
ERROR_CYCLE_DENIED = "controller.cycle_denied"
ERROR_CHILD_EXECUTION_FAILED = "controller.child_execution_failed"
ERROR_OBSERVABILITY_EMIT_FAILED = "controller.observability_emit_failed"
ERROR_DISABLED_BY_POLICY = "controller.disabled_by_policy"

KNOWN_CONTROLLER_ERRORS = {
    ERROR_ENVELOPE_INVALID,
    ERROR_CHILD_SDK_REQUIRED,
    ERROR_MAX_DEPTH_EXCEEDED,
    ERROR_MAX_FANOUT_EXCEEDED,
    ERROR_CHILD_TIMEOUT_INVALID,
    ERROR_RECURSION_DENIED,
    ERROR_CYCLE_DENIED,
    ERROR_CHILD_EXECUTION_FAILED,
    ERROR_OBSERVABILITY_EMIT_FAILED,
    ERROR_DISABLED_BY_POLICY,
}

BLOCKED_CONTROLLER_ERRORS = {
    ERROR_ENVELOPE_INVALID,
    ERROR_CHILD_SDK_REQUIRED,
    ERROR_MAX_DEPTH_EXCEEDED,
    ERROR_MAX_FANOUT_EXCEEDED,
    ERROR_CHILD_TIMEOUT_INVALID,
    ERROR_RECURSION_DENIED,
    ERROR_CYCLE_DENIED,
    ERROR_DISABLED_BY_POLICY,
}


def normalize_controller_error(text: str) -> str:
    for code in KNOWN_CONTROLLER_ERRORS:
        if code in text:
            return code
    return ERROR_CHILD_EXECUTION_FAILED


def failed_child_result(
    *,
    child: ControllerChildCall,
    error_code: str,
    requested_timeout: int | None,
    enforced_timeout: int | None,
    requested_caps: ControllerPolicyCaps,
    enforced_caps: ControllerPolicyCaps,
    summary: dict[str, Any] | None = None,
    artifact_refs: list[dict[str, Any]] | None = None,
) -> ControllerChildResult:
    return ControllerChildResult(
        target_workload=child.target_workload,
        status="failed",
        requested_timeout=requested_timeout,
        enforced_timeout=enforced_timeout,
        requested_caps=requested_caps,
        enforced_caps=enforced_caps,
        artifact_refs=list(artifact_refs or []),
        normalized_error=error_code,
        summary=dict(summary or {}),
    )


def not_attempted_results(
    *,
    children: list[ControllerChildCall],
    requested_caps: ControllerPolicyCaps,
) -> list[ControllerChildResult]:
    return [
        ControllerChildResult(
            target_workload=child.target_workload,
            status="not_attempted",
            requested_timeout=_resolve_requested_timeout(child=child, requested_caps=requested_caps),
            enforced_timeout=None,
            requested_caps=requested_caps,
            enforced_caps=None,
            artifact_refs=[],
            normalized_error=None,
            summary={},
        )
        for child in children
    ]


def resolve_run_status(*, error_code: str | None, child_results: list[ControllerChildResult]) -> ControllerRunStatus:
    if error_code is None:
        return "success"
    if error_code in BLOCKED_CONTROLLER_ERRORS and not any(item.status == "success" for item in child_results):
        return "blocked"
    return "failed"


def _resolve_requested_timeout(*, child: ControllerChildCall, requested_caps: ControllerPolicyCaps) -> int | None:
    if child.timeout_seconds is not None:
        return int(child.timeout_seconds)
    if requested_caps.child_timeout_seconds is not None:
        return int(requested_caps.child_timeout_seconds)
    return None


def read_env_int(raw: str, *, fallback: int, minimum: int) -> int:
    raw_value = str(raw or "").strip()
    if not raw_value:
        return fallback
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError(ERROR_ENVELOPE_INVALID) from exc
    if parsed < minimum:
        raise ValueError(ERROR_ENVELOPE_INVALID)
    return parsed


def parse_envelope(payload: dict[str, Any]) -> tuple[ControllerRunEnvelope | None, str | None]:
    if not isinstance(payload, dict):
        return None, ERROR_ENVELOPE_INVALID
    try:
        return ControllerRunEnvelope.model_validate(payload), None
    except ValidationError as exc:
        text = str(exc)
        if ERROR_CHILD_TIMEOUT_INVALID in text:
            return None, ERROR_CHILD_TIMEOUT_INVALID
        return None, ERROR_ENVELOPE_INVALID


def guard_child(*, child: ControllerChildCall, controller_workload_id: str, active_ancestry: list[str]) -> str | None:
    if child.target_workload == controller_workload_id:
        return ERROR_RECURSION_DENIED
    if child.target_workload in active_ancestry:
        return ERROR_CYCLE_DENIED
    if child.contract_style != CONTRACT_STYLE_SDK_V0:
        return ERROR_CHILD_SDK_REQUIRED
    return None


def requested_timeout(requested_caps: ControllerPolicyCaps, child: ControllerChildCall) -> int | None:
    if child.timeout_seconds is not None:
        return int(child.timeout_seconds)
    if requested_caps.child_timeout_seconds is not None:
        return int(requested_caps.child_timeout_seconds)
    return None


def enforced_timeout(enforced_caps: ControllerPolicyCaps, requested_timeout_value: int | None) -> int | None:
    if requested_timeout_value is None:
        return int(enforced_caps.child_timeout_seconds) if enforced_caps.child_timeout_seconds is not None else None
    if enforced_caps.child_timeout_seconds is None:
        return int(requested_timeout_value)
    return min(int(requested_timeout_value), int(enforced_caps.child_timeout_seconds))


def failed_summary(
    *,
    controller_workload_id: str,
    error_code: str,
    child_results: list[ControllerChildResult],
    requested_caps: ControllerPolicyCaps | None = None,
    enforced_caps: ControllerPolicyCaps | None = None,
) -> ControllerRunSummary:
    return ControllerRunSummary(
        controller_workload_id=controller_workload_id,
        status=resolve_run_status(error_code=error_code, child_results=child_results),
        requested_caps=requested_caps,
        enforced_caps=enforced_caps,
        child_results=child_results,
        error_code=error_code,
        metadata={},
    )


__all__ = [
    "DEFAULT_CHILD_TIMEOUT_SECONDS",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_FANOUT",
    "ERROR_CHILD_EXECUTION_FAILED",
    "ERROR_CHILD_SDK_REQUIRED",
    "ERROR_CHILD_TIMEOUT_INVALID",
    "ERROR_CYCLE_DENIED",
    "ERROR_DISABLED_BY_POLICY",
    "ERROR_ENVELOPE_INVALID",
    "ERROR_MAX_DEPTH_EXCEEDED",
    "ERROR_MAX_FANOUT_EXCEEDED",
    "ERROR_OBSERVABILITY_EMIT_FAILED",
    "ERROR_RECURSION_DENIED",
    "KNOWN_CONTROLLER_ERRORS",
    "BLOCKED_CONTROLLER_ERRORS",
    "enforced_timeout",
    "failed_child_result",
    "failed_summary",
    "guard_child",
    "normalize_controller_error",
    "not_attempted_results",
    "parse_envelope",
    "read_env_int",
    "requested_timeout",
    "resolve_run_status",
]
