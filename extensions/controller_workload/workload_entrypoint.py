from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.extensions import ExtensionManager
from orket.extensions.controller_dispatcher import ControllerDispatcher
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


class ControllerWorkload:
    async def run(self, ctx: Any, payload: dict[str, Any]) -> WorkloadResult:
        request_payload = dict(payload or {})
        dispatcher = _build_dispatcher(request_payload, ctx)
        summary = await dispatcher.dispatch(
            payload=_build_envelope_payload(request_payload, ctx),
            workspace=Path(ctx.workspace_root),
            department=_resolve_department(request_payload, ctx),
        )
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
            },
            issues=issues,
        )
