from __future__ import annotations

import os
from collections.abc import Mapping
from copy import deepcopy
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Any

from orket.application.services.extension_catalog_commands import prepare_extension_manager
from orket.extensions import controller_observability
from orket.extensions.controller_dispatcher import ControllerDispatcher
from orket.extensions.controller_dispatcher_contract import (
    ERROR_DISABLED_BY_POLICY,
    ERROR_OBSERVABILITY_EMIT_FAILED,
)
from orket_extension_sdk.controller import ControllerRunSummary
from orket_extension_sdk.workloads.controller import ControllerWorkloadRuntime


def build_controller_workload_runtime(*, ctx: Any, payload: Mapping[str, Any]) -> ControllerWorkloadRuntime:
    request_payload = dict(payload or {})
    environment = MappingProxyType(dict(os.environ))
    invocation_root = Path.cwd()
    config = getattr(ctx, "config", {})
    config_catalog = str(config.get("extensions_catalog_path") or "").strip() if isinstance(config, Mapping) else ""
    catalog_raw = str(request_payload.get("extensions_catalog_path") or config_catalog).strip()
    catalog_path = Path(catalog_raw) if catalog_raw else None
    project_root = Path(ctx.workspace_root) if catalog_raw else None

    async def dispatch(
        *,
        envelope_payload: Mapping[str, Any],
        workspace: Path,
        department: str,
    ) -> ControllerRunSummary:
        captured = deepcopy(dict(envelope_payload))
        selected_workspace, selected_department = invocation_root / workspace, str(department)
        manager = await prepare_extension_manager(catalog_path, project_root, environment=environment,
                                                  invocation_root=invocation_root)
        dispatcher = ControllerDispatcher(extension_manager=manager, environment=environment)
        return await dispatcher.dispatch(payload=captured, workspace=selected_workspace, department=selected_department)

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
        is_enabled=partial(is_controller_enabled, environment=environment),
        disabled_error_code=ERROR_DISABLED_BY_POLICY,
        observability_emit_failed_error_code=ERROR_OBSERVABILITY_EMIT_FAILED,
    )


def is_controller_enabled(*, payload: Mapping[str, Any], department: str,
                          environment: Mapping[str, str] | None = None) -> bool:
    observed = os.environ if environment is None else environment
    enable_raw = payload.get("controller_enabled", observed.get("ORKET_CONTROLLER_ENABLED", "1"))
    if _is_disabled_token(str(enable_raw)):
        return False
    allow_raw = str(observed.get("ORKET_CONTROLLER_ALLOWED_DEPARTMENTS", "")).strip()
    if not allow_raw:
        return True
    allowed = {item.strip().lower() for item in allow_raw.split(",") if item.strip()}
    return not allowed or department.strip().lower() in allowed


def _is_disabled_token(raw: str) -> bool:
    return str(raw or "").strip().lower() in {"0", "false", "no", "off", "disabled"}


__all__ = ["build_controller_workload_runtime", "is_controller_enabled"]
