from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from orket.extensions import ExtensionManager
from orket.extensions import controller_observability
from orket.extensions.controller_dispatcher import ControllerDispatcher
from orket.extensions.controller_dispatcher_contract import (
    ERROR_DISABLED_BY_POLICY,
    ERROR_OBSERVABILITY_EMIT_FAILED,
    failed_summary,
)
from orket_extension_sdk import Issue, WorkloadResult


def _resolve_department(payload: dict[str, Any], ctx: Any) -> str:
    value = str(payload.get("department") or ctx.config.get("department") or "core").strip()
    return value or "core"


def _build_envelope_payload(payload: dict[str, Any], ctx: Any) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "controller_contract_version": "controller.workload.v1",
        "controller_workload_id": str(payload.get("controller_workload_id") or ctx.workload_id),
        "parent_depth": payload.get("parent_depth", 0),
        "ancestry": payload.get("ancestry", []),
        "children": payload.get("children", []),
    }
    if "requested_caps" in payload:
        envelope["requested_caps"] = payload.get("requested_caps")
    if "metadata" in payload:
        envelope["metadata"] = payload.get("metadata")
    return envelope


def _build_dispatcher(payload: dict[str, Any], ctx: Any) -> ControllerDispatcher:
    catalog_path_raw = str(payload.get("extensions_catalog_path") or ctx.config.get("extensions_catalog_path") or "").strip()
    if not catalog_path_raw:
        return ControllerDispatcher()
    manager = ExtensionManager(catalog_path=Path(catalog_path_raw), project_root=Path(ctx.workspace_root))
    return ControllerDispatcher(extension_manager=manager)


def _is_disabled_token(raw: str) -> bool:
    return str(raw or "").strip().lower() in {"0", "false", "no", "off", "disabled"}


def _is_controller_enabled(payload: dict[str, Any], *, department: str) -> bool:
    enable_raw = payload.get("controller_enabled", os.getenv("ORKET_CONTROLLER_ENABLED", "1"))
    if _is_disabled_token(str(enable_raw)):
        return False
    allow_raw = str(os.getenv("ORKET_CONTROLLER_ALLOWED_DEPARTMENTS", "")).strip()
    if not allow_raw:
        return True
    allowed = {item.strip().lower() for item in allow_raw.split(",") if item.strip()}
    return not allowed or department.strip().lower() in allowed


class ControllerWorkload:
    async def run(self, ctx: Any, payload: dict[str, Any]) -> WorkloadResult:
        request_payload = dict(payload or {})
        department = _resolve_department(request_payload, ctx)
        envelope_payload = _build_envelope_payload(request_payload, ctx)
        if _is_controller_enabled(request_payload, department=department):
            dispatcher = _build_dispatcher(request_payload, ctx)
            summary = await dispatcher.dispatch(
                payload=envelope_payload,
                workspace=Path(ctx.workspace_root),
                department=department,
            )
        else:
            summary = failed_summary(
                controller_workload_id=str(envelope_payload.get("controller_workload_id") or ctx.workload_id),
                error_code=ERROR_DISABLED_BY_POLICY,
                child_results=[],
            )
        observability_error: str | None = None
        observability_events: list[dict[str, Any]] = []
        observability_projection: list[dict[str, Any]] = []
        try:
            observability_events = await controller_observability.emit_observability_batch(
                run_id=str(getattr(ctx, "run_id", "") or ""),
                envelope_payload=envelope_payload,
                summary=summary,
            )
            observability_projection = controller_observability.canonical_projection(observability_events)
        except (TypeError, ValueError, RuntimeError) as exc:
            observability_error = str(exc)
            summary = failed_summary(
                controller_workload_id=summary.controller_workload_id,
                error_code=ERROR_OBSERVABILITY_EMIT_FAILED,
                child_results=list(summary.child_results),
                requested_caps=summary.requested_caps,
                enforced_caps=summary.enforced_caps,
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
