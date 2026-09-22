from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from copy import copy, deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.adapters.storage.bound_filesystem import BOUND_FILESYSTEM_TOOLS
from orket.adapters.tools.builtin_connectors import BuiltInConnectorExecutor
from orket.adapters.tools.registry import (
    DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
    BuiltInConnectorMetadata,
    BuiltInConnectorRegistry,
)
from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from orket.application.services.connector_invocation_timing import ConnectorInvocationTimer
from orket.application.services.owned_http_request_service import OwnedHttpRequestService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.owned_command import CommandExecutionUncertain
from orket.core.domain.outward_authorization import OutwardAuthorization, args_hash
from orket.logging import log_event

logger = logging.getLogger(__name__)


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
    @classmethod
    async def for_workspace(cls, workspace_root: Path, *, http_allowlist: tuple[str, ...] = ()) -> OutwardConnectorService:
        """Compose the built-in connector registry at the application boundary."""
        selected_allowlist = tuple(http_allowlist)

        def compose() -> OutwardConnectorService:
            return cls(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
                       workspace_root=workspace_root.resolve(), http_allowlist=selected_allowlist)

        return await run_owned_thread(compose, label="connector-workspace-composition")

    def __init__(
        self,
        *,
        connector_registry: BuiltInConnectorRegistry,
        workspace_root: Path,
        http_allowlist: tuple[str, ...] = (),
        executor: BuiltInConnectorExecutor | None = None,
        monotonic_ns: Callable[[], int] | None = None,
    ) -> None:
        self.connector_registry = connector_registry
        self.workspace_root = workspace_root
        self._monotonic_ns = monotonic_ns if monotonic_ns is not None else RuntimeInputService().monotonic_ns
        self._clock_ref = "injected_monotonic_ns" if monotonic_ns is not None else "python.time.perf_counter_ns"
        self.executor = executor or BuiltInConnectorExecutor(
            workspace_root=workspace_root,
            command_runner=CommandProcessSupervisor(workspace_root, cancellation_event="outward_command_cancelled"),
            http_requester=OwnedHttpRequestService(),
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

    async def authorization_context(self, connector_name: str, args: dict[str, Any]) -> dict[str, Any]:
        captured, metadata, arguments = self._capture_authorization_inputs(connector_name, args)

        def collect():
            captured.validate_policy(metadata.name, arguments)
            root = str(captured.executor.workspace_root.resolve())
            if metadata.name in BOUND_FILESYSTEM_TOOLS:
                target = str(captured.executor.file_tools.async_fs._resolve_safe_path(
                    str(arguments["path"]), write=metadata.name != "read_file",
                ))
            elif metadata.name in {"http_get", "http_post"}:
                url = urlparse(str(arguments["url"]))
                target = f"http-target:{url.hostname}:{args_hash({'url': arguments['url']})}"
            else:
                target = f"workspace:{root}"
            return {
                "policy_version": "outward_connector_policy.v1", "workspace_root": root,
                "target_ref": target, "connector": asdict(metadata),
                "http_allowlist": sorted(captured.executor.http_allowlist),
            }

        return await run_owned_thread(collect, label="connector-authorization-context")

    def _capture_authorization_inputs(self, connector_name, args):
        metadata, arguments = deepcopy(self._require_metadata(connector_name)), deepcopy(args)
        captured = copy(self)
        captured.connector_registry = BuiltInConnectorRegistry([metadata])
        captured.executor = copy(self.executor)
        captured.executor.workspace_root, = capture_file_roots([self.executor.workspace_root])
        captured.executor.http_allowlist = tuple(self.executor.http_allowlist)
        if metadata.name in BOUND_FILESYSTEM_TOOLS:
            captured.executor.file_tools = copy(self.executor.file_tools)
            captured.executor.file_tools.async_fs = self.executor.file_tools.async_fs.capture()
        return captured, metadata, arguments

    async def invoke(self, connector_name: str, args: dict[str, Any]) -> dict[str, Any]:
        event_payload, _result = await self.invoke_with_result(connector_name, args)
        return event_payload

    async def invoke_with_result(
        self, connector_name: str, args: dict[str, Any], *, authorization: OutwardAuthorization | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        metadata = self._require_metadata(connector_name)
        validated_args = deepcopy(self.validate_args(metadata.name, args))
        bound = {"authorization": authorization} if authorization is not None and metadata.name in BOUND_FILESYSTEM_TOOLS else {}
        timer = ConnectorInvocationTimer(self._monotonic_ns, clock_ref=self._clock_ref)
        finished, interruption = False, "unresolved"
        process_lifetime = None
        try:
            result, outcome = await self._invoke_with_deadline(metadata, validated_args, bound)
            finished = True
        except CommandProcessCancelled as exc:
            process_lifetime, interruption = exc.lifetime.lifetime(), "cancelled"
            raise
        except CommandExecutionUncertain as exc:
            process_lifetime = exc.lifetime.lifetime()
            raise
        except asyncio.CancelledError:
            interruption = "cancelled"
            raise
        finally:
            timing = timer.finish().model_dump(mode="json")
            if not finished:
                if process_lifetime is not None:
                    timing["process_lifetime"] = process_lifetime
                self._record_interruption(metadata.name, validated_args, interruption, timing)
        event_payload = {
            "connector_name": metadata.name,
            "args_hash": args_hash(validated_args),
            "result_summary": _result_summary(result),
            **timing,
            "outcome": outcome,
        }
        return event_payload, dict(result)

    async def _invoke_with_deadline(self, metadata, args, bound):
        # Keep execution in the owning task: bound filesystem workers and the
        # shared command supervisor must finish cleanup through repeated cancellation.
        cancellation = None
        try:
            async with asyncio.timeout(float(metadata.timeout_seconds)):
                try:
                    result = await self.executor.invoke(
                        metadata.name, args, timeout_seconds=float(metadata.timeout_seconds), **bound,
                    )
                except CommandProcessCancelled as exc:
                    # Python 3.11/3.12 Timeout matches the exact CancelledError
                    # type. Preserve the typed observation outside its boundary.
                    cancellation = exc
                    raise asyncio.CancelledError from exc
        except asyncio.CancelledError:
            if cancellation is not None:
                raise cancellation from cancellation.__cause__
            raise
        except TimeoutError as exc:
            result = {"ok": False, "error": "timeout", "timeout_seconds": float(metadata.timeout_seconds)}
            if cancellation is not None:
                lifetime = cancellation.lifetime
                if not lifetime.cleanup_confirmed:
                    raise CommandExecutionUncertain(lifetime) from exc
                result["process_lifetime"] = lifetime.lifetime()
            return result, "timeout"
        if metadata.name == "run_command" and result.get("error") == "timeout":
            return result, "timeout"
        return result, "success" if bool(result.get("ok")) else "failed"

    def _record_interruption(self, name, args, observation, timing) -> None:
        try:
            # Supporting telemetry only: the effect owner retains unresolved
            # dispatch intent, with no fabricated receipt or terminal effect.
            log_event("outward_connector_interrupted", {"connector_name": name, "args_hash": args_hash(args),
                      "observation": observation, **timing}, self.workspace_root)
        except (OSError, RuntimeError, ValueError, TypeError):
            logger.exception("Unable to record interrupted connector timing for %s", name)

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


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": bool(result.get("ok"))}
    for key in ("path", "status_code", "returncode", "stdout_bytes", "stderr_bytes", "body_bytes", "timeout_seconds", "process_lifetime"):
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
