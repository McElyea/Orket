from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from orket.adapters.llm.local_model_provider import LocalModelProvider
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.providers.provider_runtime_warmup import ProviderRuntimeWarmupError, warmup_provider_model
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from providers.provider_runtime_warmup import ProviderRuntimeWarmupError, warmup_provider_model
    from orket.adapters.llm.local_model_provider import LocalModelProvider


_GUIDE_TOOL_NAME = "emit_prompt_patch"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_MODEL_LOAD_TIMEOUT_SEC = 180.0
DEFAULT_MODEL_TTL_SEC = 600
DEFAULT_MAX_PROMPT_PATCH_CHARS = 1800


@dataclass(frozen=True)
class GuideModelSpec:
    label: str
    provider: str
    model: str
    base_url: str = ""

    @classmethod
    def parse(cls, raw: str) -> "GuideModelSpec":
        parts = [part.strip() for part in str(raw or "").split("|")]
        if len(parts) not in {3, 4}:
            raise ValueError("guide spec must be label|provider|model or label|provider|model|base_url")
        label, provider, model = parts[:3]
        base_url = parts[3] if len(parts) == 4 else ""
        if not label or not provider or not model:
            raise ValueError("guide spec requires non-empty label, provider, and model")
        return cls(label=label, provider=provider, model=model, base_url=base_url)

    def to_payload(self) -> dict[str, str]:
        payload = {"label": self.label, "provider": self.provider, "model": self.model}
        if self.base_url:
            payload["base_url"] = self.base_url
        return payload


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _relativize(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _slug_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return token or "guide_candidate"


def _prompt_patch_checksum(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _extract_json_object(blob: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    text = str(blob or "").strip()
    if not text:
        return None
    if "```" in text:
        for chunk in text.split("```"):
            candidate = chunk.strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    start = 0
    while True:
        brace_index = text.find("{", start)
        if brace_index < 0:
            return None
        try:
            parsed, end = decoder.raw_decode(text[brace_index:])
        except json.JSONDecodeError:
            start = brace_index + 1
            continue
        if isinstance(parsed, dict):
            return parsed
        start = brace_index + max(end, 1)


def _extract_native_tool_payload(raw_payload: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
    tool_calls = raw_payload.get("tool_calls")
    if not isinstance(tool_calls, list):
        return None, 0
    for index, tool_call in enumerate(tool_calls):
        if not isinstance(tool_call, dict):
            continue
        function_payload = tool_call.get("function")
        if not isinstance(function_payload, dict):
            continue
        if str(function_payload.get("name") or "").strip() != _GUIDE_TOOL_NAME:
            continue
        arguments = function_payload.get("arguments")
        if isinstance(arguments, dict):
            return dict(arguments), index + 1
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                return None, index + 1
            if isinstance(parsed, dict):
                return parsed, index + 1
            return None, index + 1
    return None, len(tool_calls)


def _guide_native_tools(max_prompt_patch_chars: int) -> list[dict[str, Any]]:
    properties = {
        "candidate_label": {
            "type": "string",
            "description": "Short label for the bounded prompt patch candidate.",
        },
        "prompt_patch": {
            "type": "string",
            "description": (
                "Prompt text to append to the existing prompt surface. "
                f"Keep it under {max_prompt_patch_chars} characters."
            ),
        },
        "improvement_hypothesis": {
            "type": "string",
            "description": "Short reason this patch should improve the frozen corpus.",
        },
    }
    return [
        {
            "type": "function",
            "function": {
                "name": _GUIDE_TOOL_NAME,
                "description": "Emit exactly one bounded prompt patch candidate for the supplied target and corpus.",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": list(properties.keys()),
                    "additionalProperties": False,
                },
            },
        }
    ]


def _corpus_packet(corpus: dict[str, Any], *, target_role: str, target_model: str) -> dict[str, Any]:
    slices = corpus.get("slices") if isinstance(corpus.get("slices"), list) else []
    return {
        "corpus_id": str(corpus.get("corpus_id") or ""),
        "tool_call_contract_family": str(corpus.get("tool_call_contract_family") or ""),
        "measured_outputs": list(corpus.get("measured_outputs") or []),
        "target_role": target_role,
        "target_model": target_model,
        "slices": [
            {
                "slice_id": str(row.get("slice_id") or ""),
                "issue_id": str(row.get("issue_id") or ""),
                "role_name": str(row.get("role_name") or ""),
                "description": str(row.get("description") or ""),
                "required_action_tools": list(row.get("required_action_tools") or []),
                "required_read_paths": list(row.get("required_read_paths") or []),
                "required_write_paths": list(row.get("required_write_paths") or []),
                "required_statuses": list(row.get("required_statuses") or []),
            }
            for row in slices
            if isinstance(row, dict)
        ],
    }


def _guide_prompt(packet: dict[str, Any], *, max_prompt_patch_chars: int) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a bounded prompt-reforger guide for tool-use prompts. "
                f"Call {_GUIDE_TOOL_NAME} exactly once. "
                "You are not the runtime authority and you are not judging success. "
                "Produce one small append-only prompt patch candidate that helps the frozen tool-use corpus. "
                "Do not answer in prose, do not refuse, and do not emit more than one tool call. "
                f"Keep prompt_patch under {max_prompt_patch_chars} characters."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(packet, indent=2, ensure_ascii=False),
        },
    ]


def _normalize_candidate_payload(
    payload: dict[str, Any],
    *,
    fallback_label: str,
    max_prompt_patch_chars: int,
) -> tuple[dict[str, Any] | None, str]:
    tool_name = str(payload.get("name") or payload.get("tool") or "").strip()
    if tool_name == _GUIDE_TOOL_NAME and isinstance(payload.get("arguments"), dict):
        payload = dict(payload["arguments"])
    candidate_label = str(payload.get("candidate_label") or fallback_label or "Guide candidate").strip()
    prompt_patch = str(payload.get("prompt_patch") or "").strip()
    improvement_hypothesis = str(payload.get("improvement_hypothesis") or "").strip()
    if not prompt_patch:
        return None, "guide_model_returned_empty_prompt_patch"
    if len(prompt_patch) > max_prompt_patch_chars:
        return None, "guide_model_prompt_patch_exceeded_max_chars"
    candidate_id = f"guide_{_slug_token(fallback_label)}"
    return (
        {
            "candidate_id": candidate_id,
            "label": candidate_label,
            "selection_kind": "guide_model",
            "prompt_patch": prompt_patch,
            "prompt_patch_checksum": _prompt_patch_checksum(prompt_patch),
            "improvement_hypothesis": improvement_hypothesis,
        },
        "",
    )


async def _invoke_guide_model(
    *,
    guide_spec: GuideModelSpec,
    runtime_payload: dict[str, Any],
    packet: dict[str, Any],
    timeout_sec: int,
    max_prompt_patch_chars: int,
) -> tuple[str, str, str, dict[str, Any], dict[str, Any] | None, str]:
    provider = LocalModelProvider(
        model=str(runtime_payload.get("requested_model") or guide_spec.model),
        temperature=0.0,
        seed=7,
        timeout=max(1, int(timeout_sec)),
        provider=guide_spec.provider,
        base_url=str(runtime_payload.get("base_url") or guide_spec.base_url or ""),
    )
    response_content = ""
    response_raw: dict[str, Any] = {}
    try:
        response = await provider.complete(
            _guide_prompt(packet, max_prompt_patch_chars=max_prompt_patch_chars),
            runtime_context={
                "local_prompt_task_class": "strict_json",
                "protocol_governed_enabled": True,
                "native_tools": _guide_native_tools(max_prompt_patch_chars),
                "native_tool_choice": "required",
                "native_payload_overrides": {"reasoning_effort": "none"},
            },
        )
        response_content = str(getattr(response, "content", "") or "")
        response_raw = dict(getattr(response, "raw", {}) or {})
        tool_payload, tool_call_count = _extract_native_tool_payload(response_raw)
        response_raw["guide_tool_call_count"] = int(tool_call_count)
        if tool_payload is not None:
            return "primary", "success", response_content, response_raw, tool_payload, ""
        content_payload = _extract_json_object(response_content)
        if content_payload is not None:
            return "degraded", "partial success", response_content, response_raw, content_payload, ""
        return (
            "degraded",
            "failure",
            response_content,
            response_raw,
            None,
            "guide_model_did_not_emit_parseable_candidate",
        )
    except Exception as exc:  # pragma: no cover - live-path failure recording
        response_raw = {"error": str(exc)}
        return "blocked", "environment blocker", "", response_raw, None, str(exc)
    finally:
        await provider.close()


def generate_guide_candidate(
    *,
    repo_root: Path,
    corpus: dict[str, Any],
    corpus_ref: str,
    target_role: str,
    target_model: str,
    guide_spec: GuideModelSpec,
    out_path: Path | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    model_load_timeout_sec: float = DEFAULT_MODEL_LOAD_TIMEOUT_SEC,
    model_ttl_sec: int = DEFAULT_MODEL_TTL_SEC,
    max_prompt_patch_chars: int = DEFAULT_MAX_PROMPT_PATCH_CHARS,
) -> dict[str, Any]:
    packet = _corpus_packet(corpus, target_role=target_role, target_model=target_model)
    try:
        runtime_payload = warmup_provider_model(
            provider=guide_spec.provider,
            requested_model=guide_spec.model,
            base_url=guide_spec.base_url or None,
            timeout_s=float(timeout_sec),
            auto_select_model=False,
            auto_load_local_model=True,
            model_load_timeout_s=float(model_load_timeout_sec),
            model_ttl_sec=int(model_ttl_sec),
        )
        warmup_error = ""
    except ProviderRuntimeWarmupError as exc:
        runtime_payload = {
            "requested_provider": guide_spec.provider,
            "requested_model": guide_spec.model,
            "resolved_model": "",
            "base_url": guide_spec.base_url,
            "status": "BLOCKED",
            "resolution_mode": "warmup_failed",
        }
        warmup_error = str(exc)

    observed_path = "blocked"
    observed_result = "environment blocker"
    response_content = ""
    response_raw: dict[str, Any] = {}
    normalized_candidate: dict[str, Any] | None = None
    blocking_error = warmup_error

    if str(runtime_payload.get("status") or "").strip().upper() == "OK":
        observed_path, observed_result, response_content, response_raw, raw_candidate, blocking_error = asyncio.run(
            _invoke_guide_model(
                guide_spec=guide_spec,
                runtime_payload=runtime_payload,
                packet=packet,
                timeout_sec=int(timeout_sec),
                max_prompt_patch_chars=int(max_prompt_patch_chars),
            )
        )
        normalized_candidate, candidate_error = _normalize_candidate_payload(
            raw_candidate or {},
            fallback_label=guide_spec.label,
            max_prompt_patch_chars=int(max_prompt_patch_chars),
        )
        if normalized_candidate is None:
            blocking_error = candidate_error or blocking_error or "guide_candidate_invalid"
            if observed_path != "blocked":
                observed_path = "degraded"
                observed_result = "failure"
        else:
            blocking_error = ""
    else:
        blocking_error = warmup_error or f"guide_model_unavailable:{guide_spec.provider}:{guide_spec.model}"

    payload = {
        "schema_version": "prompt_reforger_guide_candidate_generation.v1",
        "generated_at_utc": _now_utc_iso(),
        "proof_type": "live",
        "observed_path": observed_path,
        "observed_result": observed_result,
        "blocking_error": blocking_error,
        "guide_spec": guide_spec.to_payload(),
        "runtime_target": {
            "requested_provider": str(runtime_payload.get("requested_provider") or guide_spec.provider),
            "requested_model": str(runtime_payload.get("requested_model") or guide_spec.model),
            "resolved_model": str(runtime_payload.get("resolved_model") or runtime_payload.get("model_id") or ""),
            "base_url": str(runtime_payload.get("base_url") or guide_spec.base_url or ""),
            "status": str(runtime_payload.get("status") or ""),
            "resolution_mode": str(runtime_payload.get("resolution_mode") or ""),
        },
        "target_role": target_role,
        "target_model": target_model,
        "corpus_ref": corpus_ref,
        "generation_packet": packet,
        "request_messages": _guide_prompt(packet, max_prompt_patch_chars=int(max_prompt_patch_chars)),
        "guide_response": {
            "content": response_content,
            "raw": _json_safe(response_raw),
        },
        "generated_candidate": normalized_candidate or {},
    }
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
        payload["artifact_ref"] = _relativize(out_path, repo_root)
    return payload


__all__ = [
    "DEFAULT_MAX_PROMPT_PATCH_CHARS",
    "DEFAULT_MODEL_LOAD_TIMEOUT_SEC",
    "DEFAULT_MODEL_TTL_SEC",
    "DEFAULT_TIMEOUT_SEC",
    "GuideModelSpec",
    "generate_guide_candidate",
]
