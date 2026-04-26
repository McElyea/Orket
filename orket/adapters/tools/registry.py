from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


ConnectorRiskLevel = Literal["read", "write", "destructive", "network", "command"]
CONNECTOR_RISK_LEVELS: frozenset[str] = frozenset({"read", "write", "destructive", "network", "command"})


@dataclass(frozen=True)
class ToolArgumentSchema:
    tool_name: str
    required_args: tuple[str, ...]
    recoverable: bool = False
    greedy_string_arg: str | None = None
    missing_reason: str | None = None


@dataclass(frozen=True)
class BuiltInConnectorMetadata:
    name: str
    description: str
    args_schema: dict[str, Any]
    risk_level: ConnectorRiskLevel
    pii_fields: tuple[str, ...] = ()
    timeout_seconds: float = 30.0


class BuiltInConnectorRegistry:
    def __init__(self, connectors: list[BuiltInConnectorMetadata] | None = None) -> None:
        self._connectors: dict[str, BuiltInConnectorMetadata] = {}
        for connector in connectors or []:
            self.register(connector)

    def register(self, connector: BuiltInConnectorMetadata) -> None:
        name = str(connector.name or "").strip()
        if not name:
            raise ValueError("connector name is required")
        if connector.risk_level not in CONNECTOR_RISK_LEVELS:
            raise ValueError(f"unsupported connector risk_level: {connector.risk_level}")
        if float(connector.timeout_seconds) <= 0:
            raise ValueError("connector timeout_seconds must be positive")
        self._connectors[name] = connector

    def get(self, name: str) -> BuiltInConnectorMetadata | None:
        return self._connectors.get(str(name or "").strip())

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._connectors))

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "description": connector.description,
                "args_schema": connector.args_schema,
                "risk_level": connector.risk_level,
                "pii_fields": list(connector.pii_fields),
                "timeout_seconds": connector.timeout_seconds,
            }
            for name, connector in sorted(self._connectors.items())
        }


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
            tool_name="create_directory",
            required_args=("path",),
            recoverable=True,
            missing_reason="missing_path",
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


def _string_property(name: str) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "title": name}


def _object_schema(required: tuple[str, ...], properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "additionalProperties": False,
        "properties": properties or {name: _string_property(name) for name in required},
    }


_PATH_SCHEMA = _object_schema(("path",), {"path": _string_property("path")})
_WRITE_FILE_SCHEMA = _object_schema(
    ("path", "content"),
    {
        "path": _string_property("path"),
        "content": {
            "anyOf": [{"type": "string"}, {"type": "object"}],
            "title": "content",
        },
    },
)
_RUN_COMMAND_SCHEMA = _object_schema(
    ("command",),
    {
        "command": {
            "anyOf": [
                {"type": "string", "minLength": 1},
                {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
            ],
            "title": "command",
        }
    },
)
_HTTP_GET_SCHEMA = _object_schema(("url",), {"url": _string_property("url")})
_HTTP_POST_SCHEMA = _object_schema(
    ("url", "body"),
    {
        "url": _string_property("url"),
        "body": {
            "anyOf": [{"type": "string"}, {"type": "object"}],
            "title": "body",
        },
    },
)


DEFAULT_BUILTIN_CONNECTOR_REGISTRY = BuiltInConnectorRegistry(
    [
        BuiltInConnectorMetadata(
            name="read_file",
            description="Read a workspace file.",
            args_schema=_PATH_SCHEMA,
            risk_level="read",
        ),
        BuiltInConnectorMetadata(
            name="write_file",
            description="Write a workspace file.",
            args_schema=_WRITE_FILE_SCHEMA,
            risk_level="write",
            pii_fields=("content",),
        ),
        BuiltInConnectorMetadata(
            name="create_directory",
            description="Create a workspace directory.",
            args_schema=_PATH_SCHEMA,
            risk_level="write",
        ),
        BuiltInConnectorMetadata(
            name="delete_file",
            description="Delete a workspace file.",
            args_schema=_PATH_SCHEMA,
            risk_level="destructive",
        ),
        BuiltInConnectorMetadata(
            name="run_command",
            description="Run a command through the governed runtime.",
            args_schema=_RUN_COMMAND_SCHEMA,
            risk_level="command",
            pii_fields=("command",),
        ),
        BuiltInConnectorMetadata(
            name="http_get",
            description="Make an allowlisted HTTP GET request.",
            args_schema=_HTTP_GET_SCHEMA,
            risk_level="network",
            pii_fields=("url",),
        ),
        BuiltInConnectorMetadata(
            name="http_post",
            description="Make an allowlisted HTTP POST request.",
            args_schema=_HTTP_POST_SCHEMA,
            risk_level="network",
            pii_fields=("url", "body"),
        ),
    ]
)
