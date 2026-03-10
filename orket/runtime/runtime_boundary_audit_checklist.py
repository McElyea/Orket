from __future__ import annotations

from pathlib import Path
from typing import Any


_ALLOWED_EXCEPTION_POLICIES = {
    "log_and_raise",
    "log_and_return_error",
    "log_and_continue",
    "fail_closed",
}
_ALLOWED_BOUNDARY_TYPES = {"api_endpoint", "cli_entrypoint", "background_loop", "webhook_handler"}

_BOUNDARY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "boundary_id": "BND-API-ENTRY",
        "boundary_type": "api_endpoint",
        "path": "orket/interfaces/api.py",
        "owner": "interfaces",
        "exception_policy": "log_and_return_error",
        "required_context_fields": ["request_id", "route"],
    },
    {
        "boundary_id": "BND-CLI-MAIN",
        "boundary_type": "cli_entrypoint",
        "path": "main.py",
        "owner": "runtime",
        "exception_policy": "log_and_raise",
        "required_context_fields": ["run_id", "command"],
    },
    {
        "boundary_id": "BND-SERVER-ENTRY",
        "boundary_type": "cli_entrypoint",
        "path": "server.py",
        "owner": "runtime",
        "exception_policy": "log_and_raise",
        "required_context_fields": ["service", "port"],
    },
    {
        "boundary_id": "BND-WEBHOOK-GITEA",
        "boundary_type": "webhook_handler",
        "path": "orket/adapters/vcs/gitea_webhook_handler.py",
        "owner": "adapters",
        "exception_policy": "log_and_continue",
        "required_context_fields": ["event_type", "issue_id"],
    },
    {
        "boundary_id": "BND-BACKGROUND-LIVE-LOOP",
        "boundary_type": "background_loop",
        "path": "orket/application/services/gitea_state_worker.py",
        "owner": "application",
        "exception_policy": "log_and_continue",
        "required_context_fields": ["loop_name", "cycle_id"],
    },
)


def runtime_boundary_audit_checklist_snapshot() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "boundaries": [dict(row) for row in _BOUNDARY_ROWS],
    }


def validate_runtime_boundary_audit_checklist(
    payload: dict[str, Any] | None = None,
    *,
    workspace_root: Path | None = None,
) -> tuple[str, ...]:
    checklist = dict(payload or runtime_boundary_audit_checklist_snapshot())
    rows = list(checklist.get("boundaries") or [])
    if not rows:
        raise ValueError("E_RUNTIME_BOUNDARY_CHECKLIST_EMPTY")

    workspace = workspace_root.resolve() if workspace_root is not None else None
    boundary_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_RUNTIME_BOUNDARY_ROW_SCHEMA")
        boundary_id = str(row.get("boundary_id") or "").strip()
        boundary_type = str(row.get("boundary_type") or "").strip().lower()
        path = str(row.get("path") or "").strip()
        owner = str(row.get("owner") or "").strip()
        exception_policy = str(row.get("exception_policy") or "").strip().lower()
        context_fields = [str(token).strip() for token in row.get("required_context_fields", []) if str(token).strip()]

        if not boundary_id or not path or not owner:
            raise ValueError("E_RUNTIME_BOUNDARY_ROW_SCHEMA")
        if boundary_type not in _ALLOWED_BOUNDARY_TYPES:
            raise ValueError(f"E_RUNTIME_BOUNDARY_TYPE_INVALID:{boundary_id}")
        if exception_policy not in _ALLOWED_EXCEPTION_POLICIES:
            raise ValueError(f"E_RUNTIME_BOUNDARY_EXCEPTION_POLICY_INVALID:{boundary_id}")
        if not context_fields:
            raise ValueError(f"E_RUNTIME_BOUNDARY_CONTEXT_FIELDS_REQUIRED:{boundary_id}")
        if workspace is not None and not (workspace / path).exists():
            raise ValueError(f"E_RUNTIME_BOUNDARY_PATH_MISSING:{boundary_id}:{path}")

        boundary_ids.append(boundary_id)

    if len(set(boundary_ids)) != len(boundary_ids):
        raise ValueError("E_RUNTIME_BOUNDARY_DUPLICATE_ID")
    return tuple(sorted(boundary_ids))
