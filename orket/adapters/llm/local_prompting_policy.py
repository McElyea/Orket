from __future__ import annotations
import asyncio
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from orket.adapters.llm.local_prompting_lmstudio_session import (
    resolve_lmstudio_session_settings,
)
from orket.runtime.local_prompt_profiles import (
    DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH,
    LocalPromptProfile,
    load_local_prompt_profile_registry_file,
)

E_LOCAL_PROMPT_MODE_INVALID = "E_LOCAL_PROMPT_MODE_INVALID"
E_LOCAL_PROMPT_TASK_CLASS_INVALID = "E_LOCAL_PROMPT_TASK_CLASS_INVALID"
E_LOCAL_PROMPT_ROLE_FORBIDDEN = "E_LOCAL_PROMPT_ROLE_FORBIDDEN"
E_LOCAL_PROMPT_REPEAT_PENALTY = "E_LOCAL_PROMPT_REPEAT_PENALTY"
E_LOCAL_PROMPT_PROFILE_RESOLUTION = "E_LOCAL_PROMPT_PROFILE_RESOLUTION"
E_LOCAL_PROMPT_PROFILE_REQUIRED = "E_LOCAL_PROMPT_PROFILE_REQUIRED"
_TASK_CLASS_VALUES = {"strict_json", "tool_call", "concise_text", "reasoning"}
_MODE_VALUES = {"shadow", "compat", "enforce"}
_REGISTRY_CACHE_LOCK = threading.Lock()
_REGISTRY_CACHE: dict[str, Any] = {}


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
    return token in {"1", "true", "yes", "on", "enabled"}


def _canonicalize_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    # LP-02 requires trailing whitespace normalization before hashing.
    return "\n".join(line.rstrip(" \t") for line in normalized.split("\n"))


def _canonicalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str((message or {}).get("role") or "").strip().lower()
        content = _canonicalize_text(str((message or {}).get("content") or ""))
        normalized.append({"role": role, "content": content})
    return normalized


def _render_hash(messages: list[dict[str, str]]) -> tuple[str, int]:
    canonical = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = canonical.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return digest, len(payload)


def _profile_registry_with_hash(path: Path) -> tuple[Any, str]:
    resolved = path.resolve()
    stat = resolved.stat()
    stamp = f"{resolved}:{stat.st_mtime_ns}:{stat.st_size}"
    with _REGISTRY_CACHE_LOCK:
        cached_stamp = str(_REGISTRY_CACHE.get("stamp") or "")
        if cached_stamp == stamp and _REGISTRY_CACHE.get("registry") is not None:
            return _REGISTRY_CACHE["registry"], str(_REGISTRY_CACHE["hash"])
    registry = load_local_prompt_profile_registry_file(resolved)
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    with _REGISTRY_CACHE_LOCK:
        _REGISTRY_CACHE["stamp"] = stamp
        _REGISTRY_CACHE["registry"] = registry
        _REGISTRY_CACHE["hash"] = digest
    return registry, digest


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


def _dedupe_in_order(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Deterministic approximation for local profile budget enforcement.
    return max(1, len(text.encode("utf-8")) // 4)


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
    for row, cost in zip(reversed(rows[1:]), reversed(costs[1:])):
        if keep_cost + cost > context_budget_tokens:
            trimmed += 1
            continue
        keep.insert(1, row)
        keep_cost += cost
    return keep, trimmed


def _provider_default_stops(provider_backend: str) -> list[str]:
    if provider_backend == "openai_compat":
        return ["</s>"]
    return ["<|eot_id|>", "</s>"]


def _effective_stops(provider_backend: str, profile: LocalPromptProfile, task_class: str) -> list[str]:
    sentinel = list(profile.stop_sequences_by_task_class.get(task_class) or [])
    provider_defaults = _provider_default_stops(provider_backend)
    return _dedupe_in_order(sentinel + provider_defaults)


def _sampling_bundle(profile: LocalPromptProfile, task_class: str) -> dict[str, Any]:
    bundle = dict(profile.sampling_bundles[task_class].model_dump())
    if task_class == "strict_json" and float(bundle.get("repeat_penalty", 1.0)) > 1.05:
        raise ValueError(f"{E_LOCAL_PROMPT_REPEAT_PENALTY}:{bundle['repeat_penalty']}")
    return bundle


@dataclass
class LocalPromptingPolicyResult:
    mode: str
    task_class: str
    messages: list[dict[str, str]]
    profile_id: str
    template_family: str
    template_version: str
    template_hash: str
    template_hash_alg: str
    rendered_prompt_byte_count: int
    stop_sequences_by_task_class: dict[str, list[str]]
    effective_stop_sequences: list[str]
    sampling_bundle: dict[str, Any]
    history_policy: str
    allows_thinking_blocks: bool
    thinking_block_format: str
    intro_phrase_denylist: list[str]
    lmstudio_session_mode: str
    lmstudio_session_id: str
    resolution_path: str
    profile_registry_snapshot_hash: str
    warnings: list[str]

    def openai_payload_overrides(self) -> dict[str, Any]:
        if not self.sampling_bundle:
            if self.effective_stop_sequences:
                return {"stop": list(self.effective_stop_sequences)}
            return {}
        overrides: dict[str, Any] = {
            "temperature": float(self.sampling_bundle.get("temperature", 0.2)),
            "top_p": float(self.sampling_bundle.get("top_p", 1.0)),
            "max_tokens": int(self.sampling_bundle.get("max_output_tokens", 256)),
        }
        if self.effective_stop_sequences:
            overrides["stop"] = list(self.effective_stop_sequences)
        seed_policy = str(self.sampling_bundle.get("seed_policy") or "")
        if seed_policy == "fixed" and self.sampling_bundle.get("seed_value") is not None:
            overrides["seed"] = int(self.sampling_bundle["seed_value"])
        if self.lmstudio_session_mode != "none" and self.lmstudio_session_id:
            overrides["session_id"] = self.lmstudio_session_id
        return overrides

    def ollama_options_overrides(self) -> dict[str, Any]:
        if not self.sampling_bundle:
            if self.effective_stop_sequences:
                return {"stop": list(self.effective_stop_sequences)}
            return {}
        overrides: dict[str, Any] = {
            "temperature": float(self.sampling_bundle.get("temperature", 0.2)),
            "top_p": float(self.sampling_bundle.get("top_p", 1.0)),
            "top_k": int(self.sampling_bundle.get("top_k", 40)),
            "repeat_penalty": float(self.sampling_bundle.get("repeat_penalty", 1.0)),
            "num_predict": int(self.sampling_bundle.get("max_output_tokens", 256)),
        }
        if self.effective_stop_sequences:
            overrides["stop"] = list(self.effective_stop_sequences)
        seed_policy = str(self.sampling_bundle.get("seed_policy") or "")
        if seed_policy == "fixed" and self.sampling_bundle.get("seed_value") is not None:
            overrides["seed"] = int(self.sampling_bundle["seed_value"])
        return overrides

    def telemetry(self) -> dict[str, Any]:
        return {
            "local_prompting_mode": self.mode,
            "task_class": self.task_class,
            "profile_id": self.profile_id,
            "template_family": self.template_family,
            "template_version": self.template_version,
            "template_hash": self.template_hash,
            "template_hash_alg": self.template_hash_alg,
            "rendered_prompt_byte_count": self.rendered_prompt_byte_count,
            "sampling_bundle": dict(self.sampling_bundle),
            "stop_sequences_by_task_class": dict(self.stop_sequences_by_task_class),
            "effective_stop_sequences": list(self.effective_stop_sequences),
            "history_policy": self.history_policy,
            "allows_thinking_blocks": self.allows_thinking_blocks,
            "thinking_block_format": self.thinking_block_format,
            "intro_phrase_denylist": list(self.intro_phrase_denylist),
            "local_prompt_allows_thinking_blocks": self.allows_thinking_blocks,
            "local_prompt_thinking_block_format": self.thinking_block_format,
            "local_prompt_intro_denylist": list(self.intro_phrase_denylist),
            "lmstudio_session_mode": self.lmstudio_session_mode,
            "lmstudio_session_id_present": bool(self.lmstudio_session_id),
            "profile_resolution_path": self.resolution_path,
            "profile_registry_snapshot_hash": self.profile_registry_snapshot_hash,
            "local_prompting_warnings": list(self.warnings),
        }


async def resolve_local_prompting_policy(
    *,
    provider_backend: str,
    model: str,
    messages: list[dict[str, str]],
    runtime_context: dict[str, Any] | None = None,
) -> LocalPromptingPolicyResult:
    context = dict(runtime_context or {})
    mode = _normalize_mode(context.get("local_prompting_mode") or os.getenv("ORKET_LOCAL_PROMPTING_MODE") or "shadow")
    task_class = _resolve_task_class(context)
    strict_task = task_class in {"strict_json", "tool_call"}
    allow_fallback = _parse_bool(
        context.get("local_prompting_allow_fallback") or os.getenv("ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK")
    )
    fallback_profile_id = str(
        context.get("local_prompting_fallback_profile_id")
        or os.getenv("ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID")
        or ""
    ).strip()
    override_profile_id = str(
        context.get("local_prompt_profile_id") or os.getenv("ORKET_LOCAL_PROMPT_PROFILE_ID") or ""
    ).strip()
    registry_path = Path(
        str(
            context.get("local_prompt_profile_registry_path")
            or os.getenv("ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH")
            or DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH
        )
    )
    registry, registry_hash = await asyncio.to_thread(_profile_registry_with_hash, registry_path)
    lmstudio_session_mode, lmstudio_session_id = resolve_lmstudio_session_settings(context, provider_backend)
    try:
        resolved = registry.resolve_profile(
            provider=provider_backend,
            model=model,
            override_profile_id=override_profile_id or None,
            allow_fallback=allow_fallback,
            fallback_profile_id=fallback_profile_id or None,
        )
    except ValueError as exc:
        if strict_task or mode == "enforce":
            raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_REQUIRED}:{exc}") from exc
        normalized_messages = _canonicalize_messages(messages)
        template_hash, byte_count = _render_hash(normalized_messages)
        return LocalPromptingPolicyResult(
            mode=mode,
            task_class=task_class,
            messages=normalized_messages,
            profile_id="unresolved",
            template_family="unknown",
            template_version="unknown",
            template_hash=template_hash,
            template_hash_alg="sha256",
            rendered_prompt_byte_count=byte_count,
            stop_sequences_by_task_class={},
            effective_stop_sequences=[],
            sampling_bundle={},
            history_policy="unknown",
            allows_thinking_blocks=False,
            thinking_block_format="none",
            intro_phrase_denylist=[],
            lmstudio_session_mode=lmstudio_session_mode,
            lmstudio_session_id=lmstudio_session_id,
            resolution_path="unresolved",
            profile_registry_snapshot_hash=registry_hash,
            warnings=[f"{E_LOCAL_PROMPT_PROFILE_RESOLUTION}:{exc}"],
        )
    resolved_messages = _canonicalize_messages(messages)
    if resolved.profile.system_prompt_mode == "user_injection":
        resolved_messages = _apply_user_injection(resolved_messages)
    resolved_messages, trimmed_count = _trim_messages_by_budget(
        resolved_messages,
        context_budget_tokens=int(resolved.profile.context_budget_tokens),
    )
    role_violation = _role_forbidden_error(resolved_messages, resolved.profile)
    if role_violation:
        tool_path = task_class == "tool_call"
        if mode == "enforce" or (mode == "compat" and tool_path):
            raise ValueError(f"{E_LOCAL_PROMPT_ROLE_FORBIDDEN}:{role_violation}")
    warnings: list[str] = []
    if trimmed_count > 0:
        warnings.append(f"context_trimmed:{trimmed_count}")
    if lmstudio_session_mode in {"context", "fixed"} and not lmstudio_session_id:
        warnings.append("lmstudio_session_id_missing")
    effective_stops = _effective_stops(provider_backend, resolved.profile, task_class)
    sampling_bundle = _sampling_bundle(resolved.profile, task_class)
    template_hash, byte_count = _render_hash(resolved_messages)
    return LocalPromptingPolicyResult(
        mode=mode,
        task_class=task_class,
        messages=resolved_messages,
        profile_id=resolved.profile.profile_id,
        template_family=resolved.profile.template_family,
        template_version=resolved.profile.template_version,
        template_hash=template_hash,
        template_hash_alg="sha256",
        rendered_prompt_byte_count=byte_count,
        stop_sequences_by_task_class=dict(resolved.profile.stop_sequences_by_task_class),
        effective_stop_sequences=effective_stops,
        sampling_bundle=sampling_bundle,
        history_policy=str(resolved.profile.history_policy),
        allows_thinking_blocks=bool(resolved.profile.allows_thinking_blocks),
        thinking_block_format=str(resolved.profile.thinking_block_format),
        intro_phrase_denylist=list(resolved.profile.intro_phrase_denylist),
        lmstudio_session_mode=lmstudio_session_mode,
        lmstudio_session_id=lmstudio_session_id,
        resolution_path=resolved.resolution_path,
        profile_registry_snapshot_hash=registry_hash,
        warnings=warnings,
    )
