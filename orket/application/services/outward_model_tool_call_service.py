from __future__ import annotations

import inspect
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.adapters.tools.registry import BuiltInConnectorRegistry
from orket.application.services.outward_model_observability import (
    OutwardModelObservabilityError,
    record_proposal_extraction_acceptance,
    write_model_evidence,
)
from orket.application.services.outward_run_execution_plan import current_step_index, previous_tool_results
from orket.core.domain.outward_runs import OutwardRunRecord
from orket.exceptions import ModelProviderError


class OutwardModelToolCallError(RuntimeError):
    pass


class OutwardModelClient(Protocol):
    async def complete(self, messages: list[dict[str, str]], runtime_context: dict[str, Any] | None = None) -> Any: ...


@dataclass(frozen=True)
class OutwardModelToolCallResult:
    tool_call: dict[str, Any]
    model_invocation: dict[str, Any]
    response: Any | None = None


def create_configured_model_client() -> OutwardModelClient:
    model = str(
        os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID")
        or os.getenv("ORKET_MODEL_ID")
        or os.getenv("ORKET_LLM_MODEL")
        or os.getenv("ORKET_MODEL")
        or ""
    ).strip()
    provider = str(
        os.getenv("ORKET_LLM_PROVIDER")
        or os.getenv("ORKET_MODEL_PROVIDER")
        or os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER")
        or ""
    ).strip()
    return LocalModelProvider(
        model=model,
        temperature=0.0,
        timeout=_positive_int_env("ORKET_MODEL_STREAM_REAL_TIMEOUT_S", default=300),
        provider=provider,
    )


class OutwardModelToolCallService:
    def __init__(
        self,
        *,
        connector_registry: BuiltInConnectorRegistry,
        workspace_root: Path,
        model_client_factory: Callable[[], OutwardModelClient] | None = None,
    ) -> None:
        self.connector_registry = connector_registry
        self.workspace_root = workspace_root
        self.model_client_factory = model_client_factory or create_configured_model_client

    async def produce_governed_tool_call(
        self,
        *,
        run: OutwardRunRecord,
        expected_tool: str,
        governed_tools: set[str],
    ) -> OutwardModelToolCallResult:
        clean_expected_tool = str(expected_tool or "").strip()
        clean_governed_tools = {str(tool).strip() for tool in governed_tools if str(tool).strip()}
        if not clean_expected_tool:
            raise OutwardModelToolCallError("expected governed tool is required")
        if not clean_governed_tools:
            raise OutwardModelToolCallError("run has no governed tool family")
        if clean_expected_tool not in clean_governed_tools:
            raise OutwardModelToolCallError(
                f"acceptance_contract tool is not in governed tool family: {clean_expected_tool}"
            )
        if self.connector_registry.get(clean_expected_tool) is None:
            raise OutwardModelToolCallError(f"acceptance_contract tool is not registered: {clean_expected_tool}")
        connector = self.connector_registry.get(clean_expected_tool)
        if connector is None:
            raise OutwardModelToolCallError(f"acceptance_contract tool is not registered: {clean_expected_tool}")

        messages = _prompt_messages(
            run=run,
            expected_tool=clean_expected_tool,
            governed_tools=clean_governed_tools,
            connector_registry=self.connector_registry,
        )
        runtime_context = {
            "local_prompt_task_class": "tool_call",
            "required_action_tools": sorted(clean_governed_tools),
            "native_tools": _native_tools(clean_governed_tools, self.connector_registry),
            "native_tool_choice": "required",
            "outward_run_id": run.run_id,
            "outward_namespace": run.namespace,
            "turn_number": int(run.current_turn or 1),
        }
        client = self.model_client_factory()
        response: Any | None = None
        result = "provider_error"
        error_type: str | None = None
        tool_call: dict[str, Any] | None = None
        evidence_payload: dict[str, Any] = {}
        try:
            try:
                response = await client.complete(messages, runtime_context=runtime_context)
                tool_call = _extract_model_tool_call(response)
                result = "tool_call_extracted"
            except (
                ModelProviderError,
                OutwardModelToolCallError,
                RuntimeError,
                ValueError,
                OutwardModelObservabilityError,
            ) as exc:
                error_type = exc.__class__.__name__
                if response is not None:
                    result = "invalid_tool_call"
                raise OutwardModelToolCallError(f"model governed tool call failed: {error_type}") from exc
            finally:
                evidence = await write_model_evidence(
                    workspace_root=self.workspace_root,
                    run=run,
                    messages=messages,
                    runtime_context=runtime_context,
                    response=response,
                    tool_call=tool_call,
                    result=result,
                    error_type=error_type,
                    pii_fields=connector.pii_fields,
                )
                evidence_payload = evidence.model_invocation
        finally:
            await _close_model_client(client)
        if tool_call is None:
            raise OutwardModelToolCallError("model governed tool call failed: missing extracted tool call")
        return OutwardModelToolCallResult(
            tool_call=tool_call,
            model_invocation=dict(evidence_payload),
            response=response,
        )

    async def record_proposal_extraction(
        self,
        *,
        run: OutwardRunRecord,
        model_result: OutwardModelToolCallResult,
        proposal_id: str | None,
        pii_fields: tuple[str, ...],
        acceptance_result: str = "accepted_for_proposal",
    ) -> dict[str, Any]:
        return await record_proposal_extraction_acceptance(
            workspace_root=self.workspace_root,
            run=run,
            response=model_result.response,
            tool_call=model_result.tool_call,
            pii_fields=pii_fields,
            proposal_id=proposal_id,
            acceptance_result=acceptance_result,
        )


def _prompt_messages(
    *,
    run: OutwardRunRecord,
    expected_tool: str,
    governed_tools: set[str],
    connector_registry: BuiltInConnectorRegistry,
) -> list[dict[str, str]]:
    connector_schemas = {
        name: {
            "description": metadata.description,
            "parameters": metadata.args_schema,
            "risk_level": metadata.risk_level,
        }
        for name in sorted(governed_tools)
        if (metadata := connector_registry.get(name)) is not None
    }
    user_payload = {
        "task": {
            "description": str(run.task.get("description") or ""),
            "instruction": str(run.task.get("instruction") or ""),
        },
        "current_turn_number": int(run.current_turn or 1),
        "current_sequence_step_index": current_step_index(run),
        "previous_governed_tool_results": previous_tool_results(run),
        "required_governed_tool": expected_tool,
        "available_governed_connector_schemas": connector_schemas,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are the Orket outward execution planner. Produce exactly one governed connector "
                "tool call for the requested task. Do not perform side effects yourself. If native tool "
                "calling is unavailable, respond as JSON: {\"tool\":\"<name>\",\"args\":{...}}. "
                "For later turns, use previous governed tool results as input context and produce only the "
                "next requested step. Do not repeat a previous write_file path unless the task explicitly asks."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(user_payload, sort_keys=True, indent=2),
        },
    ]


def _native_tools(governed_tools: set[str], connector_registry: BuiltInConnectorRegistry) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for name in sorted(governed_tools):
        metadata = connector_registry.get(name)
        if metadata is None:
            continue
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": metadata.name,
                    "description": metadata.description,
                    "parameters": metadata.args_schema,
                },
            }
        )
    return tools


def _extract_model_tool_call(response: Any) -> dict[str, Any]:
    raw_calls = _raw_tool_calls(_response_raw(response))
    if raw_calls:
        return _normalize_tool_call(raw_calls[0])
    content = str(getattr(response, "content", "") or "").strip()
    if not content:
        raise OutwardModelToolCallError("model response did not include a tool call")
    parsed = _parse_json_content(content)
    return _normalize_tool_call(parsed)


def _normalize_tool_call(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise OutwardModelToolCallError("model tool call must be an object")
    if "tool_call" in raw:
        return _normalize_tool_call(raw["tool_call"])
    if "governed_tool_call" in raw:
        return _normalize_tool_call(raw["governed_tool_call"])
    if isinstance(raw.get("tool_calls"), list) and raw["tool_calls"]:
        return _normalize_tool_call(raw["tool_calls"][0])

    function_payload = raw.get("function")
    if isinstance(function_payload, Mapping):
        tool = str(function_payload.get("name") or "").strip()
        args = function_payload.get("arguments")
    else:
        tool = str(raw.get("tool") or raw.get("name") or "").strip()
        args = raw.get("args", raw.get("arguments"))
    if not tool:
        raise OutwardModelToolCallError("model tool call is missing a tool name")
    normalized_args = _normalize_arguments(args)
    return {"tool": tool, "args": normalized_args}


def _normalize_arguments(args: Any) -> dict[str, Any]:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError as exc:
            raise OutwardModelToolCallError("model tool call arguments are not valid JSON") from exc
    if not isinstance(args, Mapping):
        raise OutwardModelToolCallError("model tool call arguments must be an object")
    return dict(args)


def _parse_json_content(content: str) -> Any:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise OutwardModelToolCallError("model response content is not valid JSON") from exc


async def _close_model_client(client: Any) -> None:
    close_method = getattr(client, "close", None) or getattr(client, "aclose", None)
    if not callable(close_method):
        return
    maybe_awaitable = close_method()
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


def _response_raw(response: Any | None) -> dict[str, Any]:
    raw = getattr(response, "raw", {}) if response is not None else {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _raw_tool_calls(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    calls = raw.get("tool_calls")
    return [dict(item) for item in calls if isinstance(item, Mapping)] if isinstance(calls, list) else []


def _positive_int_env(key: str, *, default: int) -> int:
    raw = str(os.getenv(key, "")).strip()
    if not raw:
        return default
    try:
        parsed = int(float(raw))
    except ValueError:
        return default
    return parsed if parsed > 0 else default

__all__ = [
    "OutwardModelClient",
    "OutwardModelToolCallError",
    "OutwardModelToolCallResult",
    "OutwardModelToolCallService",
    "create_configured_model_client",
]
