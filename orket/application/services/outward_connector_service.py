from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from orket.adapters.tools.builtin_connectors import BuiltInConnectorExecutor
from orket.adapters.tools.registry import BuiltInConnectorMetadata, BuiltInConnectorRegistry


class OutwardConnectorError(RuntimeError):
    pass


class OutwardConnectorNotFoundError(OutwardConnectorError):
    pass


class OutwardConnectorArgumentError(ValueError):
    def __init__(self, connector_name: str, errors: list[dict[str, str]]) -> None:
        super().__init__(f"invalid connector args for {connector_name}")
        self.connector_name = connector_name
        self.errors = errors


class OutwardConnectorPolicyError(PermissionError):
    def __init__(self, connector_name: str, reason: str) -> None:
        super().__init__(reason)
        self.connector_name = connector_name
        self.reason = reason


class OutwardConnectorService:
    def __init__(
        self,
        *,
        connector_registry: BuiltInConnectorRegistry,
        workspace_root: Path,
        http_allowlist: tuple[str, ...] = (),
        executor: BuiltInConnectorExecutor | None = None,
    ) -> None:
        self.connector_registry = connector_registry
        self.executor = executor or BuiltInConnectorExecutor(
            workspace_root=workspace_root,
            http_allowlist=http_allowlist,
        )

    def list_connectors(self) -> dict[str, Any]:
        return {
            "items": [self._metadata_payload(self._require_metadata(name)) for name in self.connector_registry.names()],
            "count": len(self.connector_registry.names()),
        }

    def show_connector(self, connector_name: str) -> dict[str, Any]:
        return self._metadata_payload(self._require_metadata(connector_name))

    def validate_args(self, connector_name: str, args: dict[str, Any]) -> dict[str, Any]:
        metadata = self._require_metadata(connector_name)
        if not isinstance(args, dict):
            raise OutwardConnectorArgumentError(metadata.name, [{"field": "$", "reason": "args must be an object"}])
        errors = _schema_errors(metadata.args_schema, args)
        if errors:
            raise OutwardConnectorArgumentError(metadata.name, errors)
        return dict(args)

    def validate_policy(self, connector_name: str, args: dict[str, Any]) -> None:
        metadata = self._require_metadata(connector_name)
        validated_args = self.validate_args(metadata.name, args)
        try:
            if metadata.name == "read_file":
                self.executor.file_tools.async_fs._resolve_safe_path(str(validated_args.get("path") or ""), write=False)
            elif metadata.name in {"write_file", "create_directory", "delete_file"}:
                self.executor.file_tools.async_fs._resolve_safe_path(str(validated_args.get("path") or ""), write=True)
            elif metadata.name in {"http_get", "http_post"}:
                self.executor._require_allowlisted_url(str(validated_args.get("url") or ""))
        except (PermissionError, OSError, ValueError, TypeError) as exc:
            raise OutwardConnectorPolicyError(metadata.name, str(exc)) from exc

    async def invoke(self, connector_name: str, args: dict[str, Any]) -> dict[str, Any]:
        event_payload, _result = await self.invoke_with_result(connector_name, args)
        return event_payload

    async def invoke_with_result(self, connector_name: str, args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        metadata = self._require_metadata(connector_name)
        validated_args = self.validate_args(metadata.name, args)
        try:
            result = await asyncio.wait_for(
                self.executor.invoke(
                    metadata.name,
                    validated_args,
                    timeout_seconds=float(metadata.timeout_seconds),
                ),
                timeout=float(metadata.timeout_seconds),
            )
            outcome = "success" if bool(result.get("ok")) else "failed"
        except TimeoutError:
            result = {
                "ok": False,
                "error": "timeout",
                "timeout_seconds": float(metadata.timeout_seconds),
            }
            outcome = "timeout"
        event_payload = {
            "connector_name": metadata.name,
            "args_hash": _args_hash(validated_args),
            "result_summary": _result_summary(result),
            "duration_ms": 0,
            "outcome": outcome,
        }
        return event_payload, dict(result)

    def _require_metadata(self, connector_name: str) -> BuiltInConnectorMetadata:
        metadata = self.connector_registry.get(connector_name)
        if metadata is None:
            raise OutwardConnectorNotFoundError(f"connector is not registered: {connector_name}")
        return metadata

    @staticmethod
    def _metadata_payload(metadata: BuiltInConnectorMetadata) -> dict[str, Any]:
        return {
            "name": metadata.name,
            "description": metadata.description,
            "args_schema": metadata.args_schema,
            "risk_level": metadata.risk_level,
            "pii_fields": list(metadata.pii_fields),
            "timeout_seconds": metadata.timeout_seconds,
        }


def _schema_errors(schema: dict[str, Any], args: dict[str, Any]) -> list[dict[str, str]]:
    validator = Draft202012Validator(schema)
    errors: list[dict[str, str]] = []
    for error in sorted(validator.iter_errors(args), key=_error_sort_key):
        errors.extend(_field_errors(error, args))
    return errors


def _field_errors(error: JsonSchemaValidationError, args: dict[str, Any]) -> list[dict[str, str]]:
    if error.validator == "required" and isinstance(error.validator_value, list):
        missing = [str(field) for field in error.validator_value if field not in args]
        return [{"field": field, "reason": "required"} for field in missing]
    field = ".".join(str(part) for part in error.absolute_path) or "$"
    return [{"field": field, "reason": error.message}]


def _error_sort_key(error: JsonSchemaValidationError) -> tuple[str, str]:
    return (".".join(str(part) for part in error.absolute_path), error.message)


def _args_hash(args: dict[str, Any]) -> str:
    payload = json.dumps(args, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": bool(result.get("ok"))}
    for key in ("path", "status_code", "returncode", "stdout_bytes", "stderr_bytes", "body_bytes", "timeout_seconds"):
        if key in result:
            summary[key] = result[key]
    if "content" in result:
        summary["content_bytes"] = len(str(result.get("content") or "").encode("utf-8"))
    if "error" in result:
        summary["error"] = str(result.get("error") or "")
    return summary


__all__ = [
    "OutwardConnectorArgumentError",
    "OutwardConnectorError",
    "OutwardConnectorNotFoundError",
    "OutwardConnectorPolicyError",
    "OutwardConnectorService",
]
