from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from orket_extension_sdk.controller import ControllerRunSummary, canonical_json
from orket_extension_sdk.result import Issue, WorkloadResult
from orket_extension_sdk.workload import WorkloadContext


class ControllerDispatchHook(Protocol):
    async def __call__(
        self,
        *,
        envelope_payload: Mapping[str, Any],
        workspace: Path,
        department: str,
    ) -> ControllerRunSummary:
        ...


class ControllerObservabilityHook(Protocol):
    async def __call__(
        self,
        *,
        run_id: str,
        envelope_payload: Mapping[str, Any],
        summary: ControllerRunSummary,
    ) -> list[dict[str, Any]]:
        ...


class ControllerEnablementPolicy(Protocol):
    def __call__(self, *, payload: Mapping[str, Any], department: str) -> bool:
        ...


def always_enabled(*, payload: Mapping[str, Any], department: str) -> bool:
    _ = (payload, department)
    return True


@dataclass(slots=True)
class ControllerWorkloadRuntime:
    dispatch: ControllerDispatchHook
    emit_observability: ControllerObservabilityHook
    is_enabled: ControllerEnablementPolicy = always_enabled
    disabled_error_code: str = "controller.disabled_by_policy"
    observability_emit_failed_error_code: str = "controller.observability_emit_failed"


class ControllerWorkloadRunner:
    """Optional SDK orchestration layer for controller workloads."""

    def __init__(self, *, runtime: ControllerWorkloadRuntime) -> None:
        self._runtime = runtime

    async def run(self, *, ctx: WorkloadContext, payload: Mapping[str, Any]) -> WorkloadResult:
        request_payload = dict(payload or {})
        controller_workload_id = str(request_payload.get("controller_workload_id") or ctx.workload_id)
        department = resolve_controller_department(
            request_payload,
            default_department=_context_department(ctx),
        )
        envelope_payload = build_controller_envelope_payload(
            request_payload,
            workload_id=controller_workload_id,
        )
        if self._runtime.is_enabled(payload=request_payload, department=department):
            summary = await self._runtime.dispatch(
                envelope_payload=envelope_payload,
                workspace=Path(ctx.workspace_root),
                department=department,
            )
        else:
            summary = _blocked_summary(
                controller_workload_id=controller_workload_id,
                error_code=self._runtime.disabled_error_code,
            )

        observability_error: str | None = None
        observability_events: list[dict[str, Any]] = []
        observability_projection: list[dict[str, Any]] = []
        try:
            observability_events = await self._runtime.emit_observability(
                run_id=str(getattr(ctx, "run_id", "") or ""),
                envelope_payload=envelope_payload,
                summary=summary,
            )
            observability_projection = canonical_observability_projection(observability_events)
        except (RuntimeError, TypeError, ValueError) as exc:
            observability_error = str(exc)
            summary = _observability_failed_summary(
                summary=summary,
                error_code=self._runtime.observability_emit_failed_error_code,
            )
            observability_events = []
            observability_projection = []

        summary_payload = summary.model_dump(mode="json")
        issues = []
        if summary.status != "success":
            issues.append(
                Issue(
                    code=str(summary.error_code or "controller.child_execution_failed"),
                    message="Controller workload failed.",
                    severity="error",
                )
            )
        return WorkloadResult(
            ok=summary.status == "success",
            output={
                "controller_summary": summary_payload,
                "controller_summary_canonical": summary.canonical_json(),
                "controller_observability_events": observability_events,
                "controller_observability_projection": observability_projection,
                "controller_observability_error": observability_error,
            },
            issues=issues,
        )


def resolve_controller_department(payload: Mapping[str, Any], *, default_department: str | None = None) -> str:
    value = str(payload.get("department") or default_department or "core").strip()
    return value or "core"


def build_controller_envelope_payload(payload: Mapping[str, Any], *, workload_id: str) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "controller_contract_version": "controller.workload.v1",
        "controller_workload_id": str(payload.get("controller_workload_id") or workload_id),
        "parent_depth": payload.get("parent_depth", 0),
        "ancestry": payload.get("ancestry", []),
        "children": payload.get("children", []),
    }
    if "requested_caps" in payload:
        envelope["requested_caps"] = payload.get("requested_caps")
    if "metadata" in payload:
        envelope["metadata"] = payload.get("metadata")
    return envelope


def canonical_observability_projection(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for event in events:
        if "run_id" not in event:
            raise ValueError("controller.observability_event_invalid")
        event_without_run_id = {key: value for key, value in event.items() if key != "run_id"}
        projected.append(json.loads(canonical_json(event_without_run_id)))
    return projected


def _blocked_summary(*, controller_workload_id: str, error_code: str) -> ControllerRunSummary:
    return ControllerRunSummary(
        controller_workload_id=controller_workload_id,
        status="blocked",
        child_results=[],
        error_code=error_code,
        metadata={},
    )


def _observability_failed_summary(*, summary: ControllerRunSummary, error_code: str) -> ControllerRunSummary:
    return ControllerRunSummary(
        controller_workload_id=summary.controller_workload_id,
        status="failed",
        requested_caps=summary.requested_caps,
        enforced_caps=summary.enforced_caps,
        child_results=list(summary.child_results),
        error_code=error_code,
        metadata=dict(summary.metadata),
    )


def _context_department(ctx: WorkloadContext) -> str | None:
    config = getattr(ctx, "config", {})
    if not isinstance(config, Mapping):
        return None
    value = str(config.get("department") or "").strip()
    return value or None


__all__ = [
    "ControllerDispatchHook",
    "ControllerEnablementPolicy",
    "ControllerObservabilityHook",
    "ControllerWorkloadRunner",
    "ControllerWorkloadRuntime",
    "always_enabled",
    "build_controller_envelope_payload",
    "canonical_observability_projection",
    "resolve_controller_department",
]
