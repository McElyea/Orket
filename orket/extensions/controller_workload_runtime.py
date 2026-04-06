from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orket.extensions import controller_observability
from orket.extensions.controller_dispatcher import ControllerDispatcher
from orket.extensions.controller_dispatcher_contract import (
    ERROR_DISABLED_BY_POLICY,
    ERROR_OBSERVABILITY_EMIT_FAILED,
)
from orket.extensions.manager import ExtensionManager
from orket_extension_sdk.controller import ControllerRunSummary
from orket_extension_sdk.workloads.controller import ControllerWorkloadRuntime


def build_controller_workload_runtime(*, ctx: Any, payload: Mapping[str, Any]) -> ControllerWorkloadRuntime:
    request_payload = dict(payload or {})
    dispatcher = _build_dispatcher(request_payload, ctx)

    async def dispatch(
        *,
        envelope_payload: Mapping[str, Any],
        workspace: Path,
        department: str,
    ) -> ControllerRunSummary:
        return await dispatcher.dispatch(
            payload=dict(envelope_payload),
            workspace=workspace,
            department=department,
        )

    async def emit_observability(
        *,
        run_id: str,
        envelope_payload: Mapping[str, Any],
        summary: ControllerRunSummary,
    ) -> list[dict[str, Any]]:
        return await controller_observability.emit_observability_batch(
            run_id=run_id,
            envelope_payload=dict(envelope_payload),
            summary=summary,
        )

    return ControllerWorkloadRuntime(
        dispatch=dispatch,
        emit_observability=emit_observability,
        is_enabled=is_controller_enabled,
        disabled_error_code=ERROR_DISABLED_BY_POLICY,
        observability_emit_failed_error_code=ERROR_OBSERVABILITY_EMIT_FAILED,
    )


def is_controller_enabled(*, payload: Mapping[str, Any], department: str) -> bool:
    enable_raw = payload.get("controller_enabled", os.getenv("ORKET_CONTROLLER_ENABLED", "1"))
    if _is_disabled_token(str(enable_raw)):
        return False
    allow_raw = str(os.getenv("ORKET_CONTROLLER_ALLOWED_DEPARTMENTS", "")).strip()
    if not allow_raw:
        return True
    allowed = {item.strip().lower() for item in allow_raw.split(",") if item.strip()}
    return not allowed or department.strip().lower() in allowed


def _build_dispatcher(payload: Mapping[str, Any], ctx: Any) -> ControllerDispatcher:
    config = getattr(ctx, "config", {})
    config_catalog_path = ""
    if isinstance(config, Mapping):
        config_catalog_path = str(config.get("extensions_catalog_path") or "").strip()
    catalog_path_raw = str(payload.get("extensions_catalog_path") or config_catalog_path).strip()
    if not catalog_path_raw:
        return ControllerDispatcher()
    manager = ExtensionManager(catalog_path=Path(catalog_path_raw), project_root=Path(ctx.workspace_root))
    return ControllerDispatcher(extension_manager=manager)


def _is_disabled_token(raw: str) -> bool:
    return str(raw or "").strip().lower() in {"0", "false", "no", "off", "disabled"}


__all__ = ["build_controller_workload_runtime", "is_controller_enabled"]
