from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.domain.execution import ExecutionTurn


class PathResolver:
    """Stateless path resolution helpers for turn contract checks."""

    _PATH_TOOL_NAMES = {"read_file", "write_file", "list_directory", "list_dir"}

    @staticmethod
    def required_read_paths(context: dict[str, Any], workspace: Path) -> list[str]:
        existing, _ = PathResolver.partition_required_read_paths(context, workspace)
        return existing

    @staticmethod
    def missing_required_read_paths(context: dict[str, Any], workspace: Path) -> list[str]:
        _, missing = PathResolver.partition_required_read_paths(context, workspace)
        return missing

    @staticmethod
    def partition_required_read_paths(context: dict[str, Any], workspace: Path) -> tuple[list[str], list[str]]:
        required_paths = [str(path).strip() for path in (context.get("required_read_paths") or []) if str(path).strip()]
        if not required_paths:
            return [], []

        existing: list[str] = []
        missing: list[str] = []
        for rel_path in required_paths:
            candidate = (workspace / rel_path).resolve()
            if candidate.exists() and candidate.is_file():
                existing.append(rel_path)
            else:
                missing.append(rel_path)
        return existing, missing

    @staticmethod
    def required_write_paths(context: dict[str, Any]) -> list[str]:
        return [str(path).strip() for path in (context.get("required_write_paths") or []) if str(path).strip()]

    @staticmethod
    def observed_read_paths(turn: ExecutionTurn) -> list[str]:
        return [str(call.args.get("path", "")).strip() for call in turn.tool_calls if call.tool == "read_file"]

    @staticmethod
    def observed_write_paths(turn: ExecutionTurn) -> list[str]:
        return [str(call.args.get("path", "")).strip() for call in turn.tool_calls if call.tool == "write_file"]

    @staticmethod
    def workspace_constraint_violation(*, tool_name: str, args: dict[str, Any], workspace: Path) -> str | None:
        normalized_tool = str(tool_name or "").strip()
        if normalized_tool not in PathResolver._PATH_TOOL_NAMES:
            return None
        if not isinstance(args, dict):
            return f"{normalized_tool}:args_not_object"
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return f"{normalized_tool}:path_missing"
        return PathResolver._path_violation(raw_path=raw_path, workspace=workspace, tool_name=normalized_tool)

    @staticmethod
    def _path_violation(*, raw_path: str, workspace: Path, tool_name: str) -> str | None:
        path_obj = Path(raw_path)
        if path_obj.is_absolute():
            return f"{tool_name}:absolute_path"

        normalized = raw_path.replace("\\", "/")
        if ".." in [segment for segment in normalized.split("/") if segment]:
            return f"{tool_name}:path_traversal"

        workspace_root = workspace.resolve()
        candidate = (workspace_root / path_obj).resolve()
        if not candidate.is_relative_to(workspace_root):
            return f"{tool_name}:path_escape"

        symlink_check = workspace_root
        for part in path_obj.parts:
            symlink_check = symlink_check / part
            if not symlink_check.exists():
                continue
            if not symlink_check.is_symlink():
                continue
            resolved = symlink_check.resolve()
            if not resolved.is_relative_to(workspace_root):
                return f"{tool_name}:symlink_escape"
        return None
