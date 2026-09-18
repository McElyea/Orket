"""Deterministic local prompting rules over explicitly supplied request values."""
from __future__ import annotations

import hashlib
import json
import warnings
from typing import Any

from orket.adapters.llm.prompt_canonicalization import canonicalize_prompt_text
from orket.runtime.config.local_prompt_profiles import LocalPromptProfile

E_LOCAL_PROMPT_MODE_INVALID = "E_LOCAL_PROMPT_MODE_INVALID"
E_LOCAL_PROMPT_TASK_CLASS_INVALID = "E_LOCAL_PROMPT_TASK_CLASS_INVALID"
E_LOCAL_PROMPT_ROLE_FORBIDDEN = "E_LOCAL_PROMPT_ROLE_FORBIDDEN"
E_LOCAL_PROMPT_REPEAT_PENALTY = "E_LOCAL_PROMPT_REPEAT_PENALTY"
E_LOCAL_PROMPT_PROFILE_RESOLUTION = "E_LOCAL_PROMPT_PROFILE_RESOLUTION"
E_LOCAL_PROMPT_PROFILE_REQUIRED = "E_LOCAL_PROMPT_PROFILE_REQUIRED"
_TASK_CLASS_VALUES = {"strict_json", "tool_call", "concise_text", "reasoning"}
_MODE_VALUES = {"shadow", "compat", "enforce"}


def _normalize_mode(value: Any) -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "shadow": "shadow",
        "compat": "compat",
        "enforce": "enforce",
    }
    resolved = aliases.get(token)
    if not resolved:
        raise ValueError(f"{E_LOCAL_PROMPT_MODE_INVALID}:{token or '<empty>'}")
    return resolved


def _normalize_task_class(value: Any) -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    if token not in _TASK_CLASS_VALUES:
        raise ValueError(f"{E_LOCAL_PROMPT_TASK_CLASS_INVALID}:{token or '<empty>'}")
    return token


def _parse_bool(value: Any) -> bool:
    token = str(value or "").strip().lower()
    if not token:
        return False
    if token in {"1", "true", "yes", "on", "enabled"}:
        return True
    if token in {"0", "false", "no", "off", "disabled"}:
        return False
    warnings.warn(f"Unrecognized boolean token in local prompting policy: {token}", UserWarning, stacklevel=2)
    return False


def _canonicalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str((message or {}).get("role") or "").strip().lower()
        content = canonicalize_prompt_text(str((message or {}).get("content") or ""))
        normalized.append({"role": role, "content": content})
    return normalized


def _render_hash(messages: list[dict[str, str]]) -> tuple[str, int]:
    canonical = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = canonical.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return digest, len(payload)


def _render_observability_classification(*, provider: str, profile: LocalPromptProfile) -> str:
    if provider == "llama_cpp" and profile.template_family != "openai_messages":
        return "message_payload_audited"
    return "rendered_prompt_audited"


def _resolve_task_class(runtime_context: dict[str, Any]) -> str:
    explicit = str(runtime_context.get("local_prompt_task_class") or "").strip()
    if explicit:
        return _normalize_task_class(explicit)
    required_tools = [
        str(tool).strip() for tool in (runtime_context.get("required_action_tools") or []) if str(tool).strip()
    ]
    # Required tool turns are structured tool-call paths even when legacy prompt mode
    # is still active, so they must use the deterministic tool_call bundle.
    if required_tools:
        return "tool_call"
    if bool(runtime_context.get("protocol_governed_enabled")):
        return "strict_json"
    return "concise_text"


def _role_forbidden_error(messages: list[dict[str, str]], profile: LocalPromptProfile) -> str | None:
    allowed_roles = {str(role).strip().lower() for role in profile.allowed_roles if str(role).strip()}
    invalid_roles = sorted(
        {
            str((message or {}).get("role") or "").strip().lower()
            for message in messages
            if str((message or {}).get("role") or "").strip().lower() not in allowed_roles
        }
    )
    if invalid_roles:
        return ",".join(invalid_roles)
    return None


def _apply_user_injection(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    system_rows: list[str] = []
    non_system: list[dict[str, str]] = []
    for message in messages:
        role = str((message or {}).get("role") or "").strip().lower()
        content = str((message or {}).get("content") or "")
        if role == "system":
            if content.strip():
                system_rows.append(content)
            continue
        non_system.append({"role": role, "content": content})
    if not system_rows:
        return non_system
    wrapper = "[SYSTEM_INSTRUCTION_BEGIN]\n" + "\n\n".join(system_rows) + "\n[SYSTEM_INSTRUCTION_END]"
    for index, message in enumerate(non_system):
        if str(message.get("role") or "").strip().lower() == "user":
            content = str(message.get("content") or "")
            merged = wrapper if not content else f"{wrapper}\n\n{content}"
            non_system[index] = {"role": "user", "content": merged}
            return non_system
    return [{"role": "user", "content": wrapper}, *non_system]


def _collapse_adjacent_user_messages(messages: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    collapsed: list[dict[str, str]] = []
    merged_count = 0
    for message in messages:
        role = str((message or {}).get("role") or "").strip().lower()
        content = str((message or {}).get("content") or "")
        if role == "user" and collapsed and str(collapsed[-1].get("role") or "").strip().lower() == "user":
            prior_content = str(collapsed[-1].get("content") or "")
            if prior_content and content:
                collapsed[-1]["content"] = f"{prior_content}\n\n{content}"
            elif content:
                collapsed[-1]["content"] = content
            merged_count += 1
            continue
        collapsed.append({"role": role, "content": content})
    return collapsed, merged_count


def _apply_reasoning_suppression_hint(
    messages: list[dict[str, str]],
    *,
    provider_backend: str,
    model: str,
    task_class: str,
    profile_id: str,
    allows_thinking_blocks: bool,
) -> tuple[list[dict[str, str]], str | None]:
    if provider_backend != "openai_compat":
        return list(messages), None
    if task_class == "reasoning" or allows_thinking_blocks:
        return list(messages), None
    if str(profile_id or "").strip() != "openai_compat.qwen.openai_messages.v1":
        return list(messages), None
    if "qwen" not in str(model or "").strip().lower():
        return list(messages), None

    resolved = [dict(message) for message in messages]
    for index in range(len(resolved) - 1, -1, -1):
        role = str((resolved[index] or {}).get("role") or "").strip().lower()
        if role != "user":
            continue
        content = str((resolved[index] or {}).get("content") or "")
        if "/no_think" in content:
            return resolved, None
        # LM Studio's Qwen family model cards document /no_think as the
        # prompt-level reasoning suppression control for chat requests.
        resolved[index]["content"] = f"{content.rstrip()}\n\n/no_think" if content.strip() else "/no_think"
        return resolved, "qwen_no_think_prompt_hint"
    return resolved, None


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Deterministic approximation for local profile budget enforcement.
    return max(1, len(text.encode("utf-8")) // 4)


def _effective_context_budget_tokens(
    *,
    profile_id: str,
    task_class: str,
    runtime_context: dict[str, Any],
    profile_budget_tokens: int,
) -> tuple[int, str | None]:
    effective_budget = int(profile_budget_tokens)
    warning = None
    if profile_id == "openai_compat.gemma.openai_messages.v1" and task_class == "tool_call":
        required_write_paths = [
            str(path).strip()
            for path in (runtime_context.get("required_write_paths") or [])
            if str(path).strip()
        ]
        if len(required_write_paths) > 1:
            effective_budget = min(effective_budget, 2400)
            if effective_budget != int(profile_budget_tokens):
                warning = f"context_budget_cap:gemma_multi_write:{effective_budget}"
    return effective_budget, warning


def _trim_messages_by_budget(
    messages: list[dict[str, str]],
    *,
    context_budget_tokens: int,
) -> tuple[list[dict[str, str]], int]:
    if context_budget_tokens <= 0 or not messages:
        return list(messages), 0
    rows = list(messages)
    costs = [
        _estimate_tokens(str((row or {}).get("role") or "")) + _estimate_tokens(str((row or {}).get("content") or ""))
        for row in rows
    ]
    total = sum(costs)
    if total <= context_budget_tokens:
        return rows, 0
    # Preserve head context and trim middle deterministically from oldest non-head rows.
    keep = [rows[0]]
    keep_cost = costs[0]
    trimmed = 0
    for row, cost in zip(reversed(rows[1:]), reversed(costs[1:]), strict=False):
        if keep_cost + cost > context_budget_tokens:
            trimmed += 1
            continue
        keep.insert(1, row)
        keep_cost += cost
    return keep, trimmed


def _strip_prior_transcript_messages(messages: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    stripped: list[dict[str, str]] = []
    removed = 0
    for message in messages:
        content = str((message or {}).get("content") or "")
        if content.startswith("Prior Transcript JSON:\n"):
            removed += 1
            continue
        stripped.append(message)
    return stripped, removed


def _provider_default_stops(provider_backend: str) -> list[str]:
    if provider_backend == "openai_compat":
        return ["</s>"]
    return ["<|eot_id|>", "</s>"]


def _effective_stops(provider_backend: str, profile: LocalPromptProfile, task_class: str) -> list[str]:
    sentinel = list(profile.stop_sequences_by_task_class.get(task_class) or [])
    provider_defaults = _provider_default_stops(provider_backend)
    return list(dict.fromkeys(sentinel + provider_defaults))


def _sampling_bundle(profile: LocalPromptProfile, task_class: str) -> dict[str, Any]:
    bundle = dict(profile.sampling_bundles[task_class].model_dump())
    if task_class == "strict_json" and float(bundle.get("repeat_penalty", 1.0)) > 1.05:
        raise ValueError(f"{E_LOCAL_PROMPT_REPEAT_PENALTY}:{bundle['repeat_penalty']}")
    return bundle
