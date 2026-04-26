from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiofiles

from orket.application.services.outward_model_redaction import redact_prompt_messages, redact_value
from orket.core.domain.outward_runs import OutwardRunRecord

_SLUG_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class OutwardModelObservabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutwardModelEvidence:
    model_invocation: dict[str, Any]
    directory: Path
    proposal_extraction_ref: str


async def write_model_evidence(
    *,
    workspace_root: Path,
    run: OutwardRunRecord,
    messages: list[dict[str, str]],
    runtime_context: dict[str, Any],
    response: Any | None,
    tool_call: dict[str, Any] | None,
    result: str,
    error_type: str | None,
    pii_fields: tuple[str, ...],
) -> OutwardModelEvidence:
    directory = _evidence_dir(workspace_root=workspace_root, namespace=run.namespace, run_id=run.run_id)
    turn = int(run.current_turn or 1)
    refs = _evidence_refs(workspace_root=workspace_root, directory=directory, turn=turn)
    prompt_payload = {
        "schema_version": "outward_model_prompt_redacted.v1",
        "run_id": run.run_id,
        "namespace": run.namespace,
        "turn_number": turn,
        "messages": redact_prompt_messages(messages, pii_fields),
        "runtime_context": _redact(_runtime_context_payload(runtime_context)),
    }
    response_payload = _model_response_payload(
        run=run,
        response=response,
        tool_call=tool_call,
        pii_fields=pii_fields,
    )
    invocation_payload = _model_invocation_payload(
        run=run,
        result=result,
        response=response,
        tool_call=tool_call,
        error_type=error_type,
        refs=refs,
    )
    extraction_payload = _proposal_extraction_payload(
        run=run,
        response=response,
        tool_call=tool_call,
        pii_fields=pii_fields,
        proposal_id=None,
        acceptance_result="extracted_pending_proposal" if tool_call is not None else "not_extracted",
    )
    try:
        await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
        files = {
            _turn_filename("model_prompt_redacted", turn): prompt_payload,
            _turn_filename("model_response_redacted", turn): response_payload,
            _turn_filename("proposal_extraction", turn): extraction_payload,
            _turn_filename("model_invocation", turn): invocation_payload,
            "model_prompt_redacted.json": prompt_payload,
            "model_response_redacted.json": response_payload,
            "proposal_extraction.json": extraction_payload,
            "model_invocation.json": invocation_payload,
        }
        for filename, payload in files.items():
            await _write_json(directory / filename, payload)
    except OSError as exc:
        raise OutwardModelObservabilityError("model observability write failed") from exc
    invocation_hash = await _file_sha256(directory / _turn_filename("model_invocation", turn))
    evidence = dict(invocation_payload)
    evidence.update(
        {
            "model_invocation_sha256": invocation_hash,
            "model_prompt_ref": refs["prompt"],
            "model_response_ref": refs["response"],
            "proposal_extraction_ref": refs["proposal_extraction"],
        }
    )
    return OutwardModelEvidence(
        model_invocation=evidence,
        directory=directory,
        proposal_extraction_ref=refs["proposal_extraction"],
    )


async def record_proposal_extraction_acceptance(
    *,
    workspace_root: Path,
    run: OutwardRunRecord,
    response: Any | None,
    tool_call: dict[str, Any],
    pii_fields: tuple[str, ...],
    proposal_id: str | None,
    acceptance_result: str = "accepted_for_proposal",
) -> dict[str, Any]:
    directory = _evidence_dir(workspace_root=workspace_root, namespace=run.namespace, run_id=run.run_id)
    turn = int(run.current_turn or 1)
    payload = _proposal_extraction_payload(
        run=run,
        response=response,
        tool_call=tool_call,
        pii_fields=pii_fields,
        proposal_id=proposal_id,
        acceptance_result=acceptance_result,
    )
    turn_file = _turn_filename("proposal_extraction", turn)
    await _write_json(directory / turn_file, payload)
    await _write_json(directory / "proposal_extraction.json", payload)
    payload["proposal_extraction_sha256"] = await _file_sha256(directory / turn_file)
    return payload


def _model_invocation_payload(
    *,
    run: OutwardRunRecord,
    result: str,
    response: Any | None,
    tool_call: dict[str, Any] | None,
    error_type: str | None,
    refs: dict[str, str],
) -> dict[str, Any]:
    raw = _response_raw(response)
    usage = raw.get("usage") if isinstance(raw.get("usage"), Mapping) else {}
    return {
        "schema_version": "outward_model_invocation.v1",
        "result": result,
        "run_id": run.run_id,
        "namespace": run.namespace,
        "session_id": _session_id(raw),
        "turn_number": int(run.current_turn or 1),
        "provider_name": _provider_name(raw),
        "model_name": _model_name(raw),
        "prompt_token_count": _optional_int(usage.get("prompt_tokens") or raw.get("input_tokens")),
        "completion_token_count": _optional_int(usage.get("completion_tokens") or raw.get("output_tokens")),
        "duration_ms": _optional_int(raw.get("latency_ms")),
        "finish_reason": _finish_reason(raw),
        "tool_name": str((tool_call or {}).get("tool") or "") or None,
        "tool_args_hash": _args_hash((tool_call or {}).get("args")) if tool_call is not None else None,
        "model_response_content_sha256": _response_material_hash(response, raw),
        "model_invocation_ref": refs["invocation"],
        "error_type": error_type,
    }


def _model_response_payload(
    *,
    run: OutwardRunRecord,
    response: Any | None,
    tool_call: dict[str, Any] | None,
    pii_fields: tuple[str, ...],
) -> dict[str, Any]:
    raw = _response_raw(response)
    content = str(getattr(response, "content", "") or "") if response is not None else ""
    return {
        "schema_version": "outward_model_response_redacted.v1",
        "run_id": run.run_id,
        "namespace": run.namespace,
        "response_material_kind": "content" if content else "tool_calls",
        "model_response_content_sha256": _response_material_hash(response, raw),
        "content_redacted": _redact_tool_content(content, pii_fields),
        "tool_calls_redacted": _redacted_tool_calls(_raw_tool_calls(raw), pii_fields),
        "extracted_tool_call_redacted": _redacted_tool_call(tool_call, pii_fields) if tool_call else None,
    }


def _proposal_extraction_payload(
    *,
    run: OutwardRunRecord,
    response: Any | None,
    tool_call: dict[str, Any] | None,
    pii_fields: tuple[str, ...],
    proposal_id: str | None,
    acceptance_result: str,
) -> dict[str, Any]:
    raw = _response_raw(response)
    return {
        "schema_version": "outward_proposal_extraction.v1",
        "extractor_version": "outward_model_tool_call_extractor.v1",
        "run_id": run.run_id,
        "namespace": run.namespace,
        "model_response_content_sha256": _response_material_hash(response, raw),
        "extracted_tool_name": str((tool_call or {}).get("tool") or "") or None,
        "extracted_args_hash": _args_hash((tool_call or {}).get("args")) if tool_call is not None else None,
        "extracted_args_preview": _redacted_args((tool_call or {}).get("args"), pii_fields) if tool_call else None,
        "proposal_id": proposal_id,
        "acceptance_result": acceptance_result,
    }


def _runtime_context_payload(runtime_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "local_prompt_task_class": runtime_context.get("local_prompt_task_class"),
        "required_action_tools": list(runtime_context.get("required_action_tools") or []),
        "native_tool_choice": runtime_context.get("native_tool_choice"),
        "outward_run_id": runtime_context.get("outward_run_id"),
        "outward_namespace": runtime_context.get("outward_namespace"),
        "turn_number": runtime_context.get("turn_number"),
        "native_tools": runtime_context.get("native_tools"),
    }


async def _write_json(path: Path, payload: dict[str, Any]) -> None:
    async with aiofiles.open(path, mode="w", encoding="utf-8") as handle:
        await handle.write(json.dumps(payload, indent=2, sort_keys=True))
        await handle.write("\n")


async def _file_sha256(path: Path) -> str:
    data = await asyncio.to_thread(path.read_bytes)
    return hashlib.sha256(data).hexdigest()


def _evidence_dir(*, workspace_root: Path, namespace: str, run_id: str) -> Path:
    root = (workspace_root / "workspace").resolve()
    path = (root / _slug(namespace) / "runs" / _slug(run_id)).resolve()
    if not path.is_relative_to(root):
        raise OutwardModelObservabilityError("model evidence path escaped workspace root")
    return path


def _evidence_refs(*, workspace_root: Path, directory: Path, turn: int) -> dict[str, str]:
    root = workspace_root.resolve()
    return {
        "invocation": str((directory / _turn_filename("model_invocation", turn)).relative_to(root)).replace("\\", "/"),
        "prompt": str((directory / _turn_filename("model_prompt_redacted", turn)).relative_to(root)).replace("\\", "/"),
        "response": str((directory / _turn_filename("model_response_redacted", turn)).relative_to(root)).replace("\\", "/"),
        "proposal_extraction": str((directory / _turn_filename("proposal_extraction", turn)).relative_to(root)).replace("\\", "/"),
    }


def _turn_filename(stem: str, turn: int) -> str:
    return f"{stem}_turn_{max(1, int(turn))}.json"


def _slug(value: str) -> str:
    slug = _SLUG_PATTERN.sub("_", str(value or "").strip()).strip("._-")
    return slug[:120] if slug else "default"


def _response_raw(response: Any | None) -> dict[str, Any]:
    raw = getattr(response, "raw", {}) if response is not None else {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _raw_tool_calls(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    calls = raw.get("tool_calls")
    return [dict(item) for item in calls if isinstance(item, Mapping)] if isinstance(calls, list) else []


def _provider_name(raw: Mapping[str, Any]) -> str | None:
    value = raw.get("provider_name") or raw.get("provider_backend") or raw.get("provider")
    return str(value).strip() if str(value or "").strip() else None


def _model_name(raw: Mapping[str, Any]) -> str | None:
    value = raw.get("model") or raw.get("requested_model")
    return str(value).strip() if str(value or "").strip() else None


def _session_id(raw: Mapping[str, Any]) -> str | None:
    value = raw.get("orket_session_id") or raw.get("session_id")
    return str(value).strip() if str(value or "").strip() else None


def _finish_reason(raw: Mapping[str, Any]) -> str | None:
    openai_payload = raw.get("openai_compat")
    if isinstance(openai_payload, Mapping):
        choices = openai_payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
            value = choices[0].get("finish_reason")
            if str(value or "").strip():
                return str(value).strip()
    value = raw.get("finish_reason")
    return str(value).strip() if str(value or "").strip() else None


def _response_material_hash(response: Any | None, raw: Mapping[str, Any]) -> str | None:
    content = str(getattr(response, "content", "") or "") if response is not None else ""
    material = content if content else json.dumps(_raw_tool_calls(raw), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest() if material else None


def _args_hash(args: Any) -> str | None:
    if not isinstance(args, Mapping):
        return None
    payload = json.dumps(dict(args), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _redacted_tool_calls(calls: list[dict[str, Any]], pii_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [_redacted_tool_call(call, pii_fields) for call in calls]


def _redacted_tool_call(call: Any, pii_fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(call, Mapping):
        return {}
    function_payload = call.get("function")
    if isinstance(function_payload, Mapping):
        args = function_payload.get("arguments")
        return {
            "type": call.get("type", "function"),
            "function": {
                "name": function_payload.get("name"),
                "arguments": _redacted_args(_decode_args(args), pii_fields),
            },
        }
    tool = call.get("tool") or call.get("name")
    args = call.get("args", call.get("arguments"))
    return {"tool": tool, "args": _redacted_args(_decode_args(args), pii_fields)}


def _redact_tool_content(content: str, pii_fields: tuple[str, ...]) -> str:
    if not content.strip():
        return ""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return _redact(content)
    return json.dumps(_redacted_tool_call(parsed, pii_fields), sort_keys=True)


def _decode_args(args: Any) -> Any:
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args
    return args


def _redacted_args(args: Any, pii_fields: tuple[str, ...]) -> dict[str, Any] | None:
    if not isinstance(args, Mapping):
        return None
    payload = dict(args)
    for field in pii_fields:
        if field in payload:
            payload[field] = "[REDACTED]"
    return _redact(payload)


def _redact(value: Any) -> Any:
    return redact_value(value)


__all__ = [
    "OutwardModelEvidence",
    "OutwardModelObservabilityError",
    "record_proposal_extraction_acceptance",
    "write_model_evidence",
]
