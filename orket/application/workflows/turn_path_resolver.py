from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.domain.execution import ExecutionTurn


class PathResolver:
    """Stateless path resolution helpers for turn contract checks."""

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
        required_paths = [
            str(path).strip()
            for path in (context.get("required_read_paths") or [])
            if str(path).strip()
        ]
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
        return [
            str(path).strip()
            for path in (context.get("required_write_paths") or [])
            if str(path).strip()
        ]

    @staticmethod
    def observed_read_paths(turn: ExecutionTurn) -> list[str]:
        return [
            str(call.args.get("path", "")).strip()
            for call in turn.tool_calls
            if call.tool == "read_file"
        ]

    @staticmethod
    def observed_write_paths(turn: ExecutionTurn) -> list[str]:
        return [
            str(call.args.get("path", "")).strip()
            for call in turn.tool_calls
            if call.tool == "write_file"
        ]
