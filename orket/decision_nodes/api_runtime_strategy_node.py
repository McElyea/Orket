from __future__ import annotations

import hmac
import os
from datetime import timedelta
from pathlib import Path
from typing import Any


class DefaultApiRuntimeStrategyNode:
    """
    Built-in API runtime strategy node.
    Preserves existing API request/runtime decision behavior.
    """

    def security_mode(self) -> str:
        return str(os.getenv("ORKET_API_SECURITY_MODE", "compat")).strip().lower() or "compat"

    def security_profile(self) -> str:
        return str(os.getenv("ORKET_API_SECURITY_PROFILE", "production")).strip().lower() or "production"

    def allow_query_api_key_auth(self) -> bool:
        return self.security_mode() != "enforce"

    def resolve_websocket_api_key(self, header_key: str | None, query_key: str | None) -> str | None:
        if header_key:
            return header_key
        if query_key and self.allow_query_api_key_auth():
            return query_key
        return None

    def websocket_query_compat_warning_event(
        self,
        query_key_used: bool,
        *,
        input_ref: str,
        timestamp_utc: str,
    ) -> dict[str, Any] | None:
        if not query_key_used:
            return None
        if self.security_mode() != "compat":
            return None
        return {
            "event_name": "security_compat_fallback_used",
            "component": "api.websocket_auth",
            "fallback_code": "API_QUERY_AUTH_COMPAT",
            "mode": self.security_mode(),
            "reason": "query_auth_used",
            "input_ref": input_ref,
            "timestamp_utc": timestamp_utc,
        }

    def default_allowed_origins_value(self) -> str:
        return "http://localhost:5173,http://127.0.0.1:5173"

    def parse_allowed_origins(self, origins_value: str) -> list[str]:
        return [origin.strip() for origin in origins_value.split(",") if origin.strip()]

    def is_api_key_valid(self, expected_key: str | None, provided_key: str | None) -> bool:
        if expected_key:
            candidate = str(provided_key or "")
            return hmac.compare_digest(candidate, expected_key)
        if self.security_profile() == "production":
            return False
        insecure_bypass = os.getenv("ORKET_ALLOW_INSECURE_NO_API_KEY", "").strip().lower()
        return insecure_bypass in {"1", "true", "yes", "on"}

    def api_key_invalid_detail(self) -> str:
        return "Could not validate credentials"

    def resolve_asset_id(self, path: str | None, issue_id: str | None) -> str | None:
        if issue_id:
            return issue_id
        if path:
            return Path(path).stem
        return None

    def resolve_run_active_invocation(
        self,
        asset_id: str,
        build_id: str | None,
        session_id: str,
        request_type: str | None,
    ) -> dict[str, Any]:
        return {
            "method_name": "run_card",
            "kwargs": {
                "card_id": asset_id,
                "build_id": build_id,
                "session_id": session_id,
            },
        }

    def run_active_missing_asset_detail(self) -> str:
        return "No asset ID provided."

    def resolve_runs_invocation(self) -> dict[str, Any]:
        return {"method_name": "get_recent_runs", "args": []}

    def resolve_backlog_invocation(self, session_id: str) -> dict[str, Any]:
        return {"method_name": "get_session_issues", "args": [session_id]}

    def resolve_session_detail_invocation(self, session_id: str) -> dict[str, Any]:
        return {"method_name": "get_session", "args": [session_id]}

    def session_detail_not_found_error(self, session_id: str) -> dict[str, Any]:
        return {"status_code": 404}

    def resolve_session_snapshot_invocation(self, session_id: str) -> dict[str, Any]:
        return {"method_name": "get", "args": [session_id]}

    def session_snapshot_not_found_error(self, session_id: str) -> dict[str, Any]:
        return {"status_code": 404}

    def resolve_sandboxes_list_invocation(self) -> dict[str, Any]:
        return {"method_name": "get_sandboxes", "args": []}

    def resolve_sandbox_stop_invocation(self, sandbox_id: str) -> dict[str, Any]:
        return {"method_name": "stop_sandbox", "args": [sandbox_id]}

    def resolve_clear_logs_path(self) -> str:
        return "workspace/default/orket.log"

    def resolve_clear_logs_invocation(self, log_path: str) -> dict[str, Any]:
        return {"method_name": "write_file", "args": [log_path, ""]}

    def resolve_read_invocation(self, path: str) -> dict[str, Any]:
        return {"method_name": "read_file", "args": [path]}

    def read_not_found_detail(self, path: str) -> str:
        return "File not found"

    def permission_denied_detail(self, operation: str, error: str) -> str:
        return error

    def resolve_save_invocation(self, path: str, content: str) -> dict[str, Any]:
        return {"method_name": "write_file", "args": [path, content]}

    def normalize_metrics(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(snapshot)
        if "cpu" not in normalized and "cpu_percent" in normalized:
            normalized["cpu"] = normalized["cpu_percent"]
        if "memory" not in normalized and "ram_percent" in normalized:
            normalized["memory"] = normalized["ram_percent"]
        return normalized

    def calendar_window(self, now: Any) -> dict[str, str]:
        return {
            "sprint_start": (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d"),
            "sprint_end": (now + timedelta(days=4 - now.weekday())).strftime("%Y-%m-%d"),
        }

    def resolve_current_sprint(self, now: Any) -> str:
        from orket.utils import get_eos_sprint

        return get_eos_sprint(now)

    def resolve_explorer_path(self, project_root: Any, path: str) -> Any | None:
        candidate_path = path or "."
        if any(part == ".." for part in Path(candidate_path).parts):
            return None
        rel_path = candidate_path.strip("./") if candidate_path != "." else ""
        target = (project_root / rel_path).resolve()
        if not target.is_relative_to(project_root):
            return None
        return target

    def resolve_explorer_forbidden_error(self, path: str) -> dict[str, Any]:
        return {"status_code": 403}

    def resolve_explorer_missing_response(self, path: str) -> dict[str, Any]:
        return {"items": [], "path": path}

    def include_explorer_entry(self, entry_name: str) -> bool:
        if entry_name.startswith("."):
            return False
        if "__pycache__" in entry_name:
            return False
        return entry_name != "node_modules"

    def sort_explorer_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(items, key=lambda item: (not item["is_dir"], item["name"].lower()))

    def resolve_preview_target(self, path: str, issue_id: str | None) -> dict[str, str]:
        resolved_path = Path(path)
        asset_name = resolved_path.stem
        department = "core"
        if "model" in resolved_path.parts:
            model_index = resolved_path.parts.index("model")
            if len(resolved_path.parts) > model_index + 1:
                department = resolved_path.parts[model_index + 1]

        mode = "epic"
        if issue_id:
            mode = "issue"
        elif "rocks" in resolved_path.parts:
            mode = "rock"
        return {"mode": mode, "asset_name": asset_name, "department": department}

    def select_preview_build_method(self, mode: str) -> str:
        method_map = {
            "issue": "build_issue_preview",
            "rock": "build_rock_preview",
        }
        return method_map.get(mode, "build_epic_preview")

    def resolve_preview_invocation(self, target: dict[str, str], issue_id: str | None) -> dict[str, Any]:
        method_name = self.select_preview_build_method(target["mode"])
        unsupported_detail = self.preview_unsupported_detail(
            target,
            {"method_name": method_name},
        )
        if target["mode"] == "issue":
            return {
                "method_name": method_name,
                "args": [issue_id, target["asset_name"], target["department"]],
                "unsupported_detail": unsupported_detail,
            }
        return {
            "method_name": method_name,
            "args": [target["asset_name"], target["department"]],
            "unsupported_detail": unsupported_detail,
        }

    def preview_unsupported_detail(self, target: dict[str, str], invocation: dict[str, Any]) -> str:
        return f"Unsupported preview mode '{target['mode']}'."

    def resolve_chat_driver_invocation(self, message: str) -> dict[str, Any]:
        return {"method_name": "process_request", "args": [message]}

    def resolve_member_metrics_workspace(self, project_root: Any, session_id: str) -> Any:
        workspace = project_root / "workspace" / "runs" / session_id
        if workspace.exists():
            return workspace
        return project_root / "workspace" / "default"

    def resolve_sandbox_workspace(self, project_root: Any) -> Any:
        return project_root / "workspace" / "default"

    def resolve_sandbox_logs_invocation(self, sandbox_id: str, service: str | None) -> dict[str, Any]:
        return {"method_name": "get_logs", "args": [sandbox_id, service]}

    def resolve_api_workspace(self, project_root: Any) -> Any:
        return project_root / "workspace" / "default"

    def resolve_system_board(self, department: str) -> Any:
        from orket.board import get_board_hierarchy

        return get_board_hierarchy(department)

    async def resolve_system_board_async(self, department: str) -> Any:
        from orket.board import get_board_hierarchy_async

        return await get_board_hierarchy_async(department)

    def should_remove_websocket(self, exception: Exception) -> bool:
        return isinstance(exception, (RuntimeError, ValueError))

    def has_archive_selector(
        self,
        card_ids: list[str] | None,
        build_id: str | None,
        related_tokens: list[str] | None,
    ) -> bool:
        return any([bool(card_ids), bool(build_id), bool(related_tokens)])

    def archive_selector_missing_detail(self) -> str:
        return "Provide at least one selector: card_ids, build_id, or related_tokens"

    def normalize_archive_response(
        self,
        archived_ids: list[str],
        missing_ids: list[str],
        archived_count: int,
    ) -> dict[str, Any]:
        unique_archived_ids = sorted(set(archived_ids))
        unique_missing_ids = sorted(set(missing_ids))
        total_archived = archived_count + len(unique_archived_ids)
        return {
            "ok": True,
            "archived_count": total_archived,
            "archived_ids": unique_archived_ids,
            "missing_ids": unique_missing_ids,
        }
