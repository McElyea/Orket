from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolArgumentSchema:
    tool_name: str
    required_args: tuple[str, ...]
    recoverable: bool = False
    greedy_string_arg: str | None = None
    missing_reason: str | None = None


class ToolRegistry:
    def __init__(self, schemas: list[ToolArgumentSchema] | None = None) -> None:
        self._schemas: dict[str, ToolArgumentSchema] = {}
        for schema in schemas or []:
            self.register(schema)

    def register(self, schema: ToolArgumentSchema) -> None:
        tool_name = str(schema.tool_name or "").strip()
        if not tool_name:
            raise ValueError("tool_name is required")
        self._schemas[tool_name] = schema

    def get(self, tool_name: str) -> ToolArgumentSchema | None:
        return self._schemas.get(str(tool_name or "").strip())

    def recoverable_schema(self, tool_name: str) -> ToolArgumentSchema | None:
        schema = self.get(tool_name)
        if schema is None or not schema.recoverable:
            return None
        return schema

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "required_args": list(schema.required_args),
                "recoverable": schema.recoverable,
                "greedy_string_arg": schema.greedy_string_arg,
                "missing_reason": schema.missing_reason,
            }
            for name, schema in sorted(self._schemas.items())
        }


DEFAULT_TOOL_REGISTRY = ToolRegistry(
    [
        ToolArgumentSchema(
            tool_name="read_file",
            required_args=("path",),
            recoverable=True,
            missing_reason="missing_path",
        ),
        ToolArgumentSchema(
            tool_name="write_file",
            required_args=("path", "content"),
            recoverable=True,
            greedy_string_arg="content",
            missing_reason="missing_path_or_content",
        ),
        ToolArgumentSchema(
            tool_name="update_issue_status",
            required_args=("status",),
            recoverable=True,
            missing_reason="missing_status",
        ),
        ToolArgumentSchema(tool_name="create_issue", required_args=("title",)),
        ToolArgumentSchema(tool_name="add_issue_comment", required_args=("comment",)),
        ToolArgumentSchema(tool_name="get_issue_context", required_args=("issue_id",)),
    ]
)
