from __future__ import annotations

from typing import Any

from orket_extension_sdk.controller import ControllerChildCall, ControllerChildResult, ControllerPolicyCaps, ControllerRunSummary

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

KNOWN_CONTROLLER_ERRORS = {
    ERROR_ENVELOPE_INVALID,
    ERROR_CHILD_SDK_REQUIRED,
    ERROR_MAX_DEPTH_EXCEEDED,
    ERROR_MAX_FANOUT_EXCEEDED,
    ERROR_CHILD_TIMEOUT_INVALID,
    ERROR_RECURSION_DENIED,
    ERROR_CYCLE_DENIED,
    ERROR_CHILD_EXECUTION_FAILED,
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
    requested_timeout: int | None,
    enforced_timeout: int | None,
    requested_caps: ControllerPolicyCaps,
    enforced_caps: ControllerPolicyCaps,
) -> list[ControllerChildResult]:
    return [
        ControllerChildResult(
            target_workload=child.target_workload,
            status="not_attempted",
            requested_timeout=requested_timeout,
            enforced_timeout=enforced_timeout,
            requested_caps=requested_caps,
            enforced_caps=enforced_caps,
            artifact_refs=[],
            normalized_error=None,
            summary={},
        )
        for child in children
    ]


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
        status="failed",
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
    "ERROR_ENVELOPE_INVALID",
    "ERROR_MAX_DEPTH_EXCEEDED",
    "ERROR_MAX_FANOUT_EXCEEDED",
    "ERROR_RECURSION_DENIED",
    "KNOWN_CONTROLLER_ERRORS",
    "failed_child_result",
    "failed_summary",
    "normalize_controller_error",
    "not_attempted_results",
]
