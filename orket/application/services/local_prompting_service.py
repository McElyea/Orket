"""Application-owned prompt capture, registry validation and policy preparation."""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from copy import deepcopy
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.prompt_registry_reader import read_prompt_registry
from orket.application.services.local_prompting_rules import (
    E_LOCAL_PROMPT_PROFILE_REQUIRED,
    E_LOCAL_PROMPT_PROFILE_RESOLUTION,
    E_LOCAL_PROMPT_ROLE_FORBIDDEN,
    _apply_reasoning_suppression_hint,
    _apply_user_injection,
    _canonicalize_messages,
    _collapse_adjacent_user_messages,
    _effective_context_budget_tokens,
    _effective_stops,
    _normalize_mode,
    _parse_bool,
    _render_hash,
    _render_observability_classification,
    _resolve_task_class,
    _role_forbidden_error,
    _sampling_bundle,
    _strip_prior_transcript_messages,
    _trim_messages_by_budget,
)
from orket.application.services.local_prompting_session import resolve_lmstudio_session_settings
from orket.core.contracts.local_prompting import LocalPromptingPolicyResult
from orket.core.contracts.model_generation_options import (
    cap_sampling_bundle,
    request_sampling_options,
    request_stop_sequences,
)
from orket.runtime.config.compact_turn_packet import compact_turn_messages, is_compact_turn_packet
from orket.runtime.config.local_prompt_profiles import (
    DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH,
    E_LOCAL_PROMPT_PROFILE_LOAD,
    load_local_prompt_profile_registry_payload,
)


class LocalPromptingService:
    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self.environment = MappingProxyType(dict(os.environ if environment is None else environment))

    async def resolve(self, *, provider_backend: str, model: str, messages: list[dict[str, str]],
                      profile_provider: str | None = None,
                      runtime_context: dict[str, Any] | None = None) -> LocalPromptingPolicyResult:
        context, captured_messages = deepcopy(runtime_context or {}), deepcopy(messages)
        environment = self.environment
        requested_sampling = request_sampling_options(context)
        requested_stops = request_stop_sequences(context)
        mode = _normalize_mode(context.get("local_prompting_mode") or environment.get("ORKET_LOCAL_PROMPTING_MODE") or "shadow")
        task_class = _resolve_task_class(context)
        strict_task = task_class in {"strict_json", "tool_call"}
        allow_fallback = _parse_bool(
            context.get("local_prompting_allow_fallback") or environment.get("ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK")
        )
        fallback_profile_id = str(
            context.get("local_prompting_fallback_profile_id")
            or environment.get("ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID")
            or ""
        ).strip()
        override_profile_id = str(
            context.get("local_prompt_profile_id") or environment.get("ORKET_LOCAL_PROMPT_PROFILE_ID") or ""
        ).strip()
        registry_path = Path(
            str(
                context.get("local_prompt_profile_registry_path")
                or environment.get("ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH")
                or DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH
            )
        )
        lmstudio_session_mode, lmstudio_session_id = resolve_lmstudio_session_settings(context, provider_backend, environment)
        observation = await run_owned_thread(partial(read_prompt_registry, registry_path), label="local prompt registry")
        try:
            payload = json.loads(observation.content.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_LOAD}:{observation.path}:{exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_LOAD}:{observation.path}:root payload must be an object")
        registry = load_local_prompt_profile_registry_payload(payload)
        inputs = dict(provider_backend=provider_backend, model=model, messages=captured_messages, context=context,
            requested_sampling=requested_sampling, requested_stops=requested_stops, mode=mode, task_class=task_class,
            strict_task=strict_task, allow_fallback=allow_fallback, fallback_profile_id=fallback_profile_id,
            override_profile_id=override_profile_id, lmstudio_session_mode=lmstudio_session_mode,
            lmstudio_session_id=lmstudio_session_id, provider_for_profile=str(profile_provider or provider_backend or "").strip().lower())
        return _resolve_registry_policy(registry=registry, registry_hash=observation.sha256, **inputs)


async def resolve_local_prompting_policy(**kwargs: Any) -> LocalPromptingPolicyResult:
    """One-shot application entry point; retained providers own a persistent service."""
    return await LocalPromptingService().resolve(**kwargs)


def _resolve_registry_policy(*, registry, registry_hash, provider_backend, model, messages, context,
    requested_sampling, requested_stops, mode, task_class, strict_task, allow_fallback, fallback_profile_id,
    override_profile_id, lmstudio_session_mode, lmstudio_session_id, provider_for_profile):
    try:
        resolved = registry.resolve_profile(
            provider=provider_for_profile,
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
            provider=provider_for_profile,
            mode=mode,
            task_class=task_class,
            messages=normalized_messages,
            profile_id="unresolved",
            template_family="unknown",
            template_version="unknown",
            template_hash=template_hash,
            template_hash_alg="sha256",
            rendered_prompt_byte_count=byte_count,
            render_observability_classification="rendered_prompt_audited",
            stop_sequences_by_task_class={},
            effective_stop_sequences=requested_stops,
            sampling_bundle=requested_sampling,
            tool_call_mode="unknown",
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
    resolved_messages, warnings, effective_context_budget_tokens = _shape_messages(
        messages, context, resolved.profile, provider_backend, model, task_class, mode,
        lmstudio_session_mode, lmstudio_session_id)
    return _resolved_policy(resolved, resolved_messages, warnings, effective_context_budget_tokens,
        provider_backend, provider_for_profile, mode, task_class, requested_stops, requested_sampling,
        lmstudio_session_mode, lmstudio_session_id, registry_hash)


def _shape_messages(messages, context, profile, provider_backend, model, task_class, mode,
                    lmstudio_session_mode, lmstudio_session_id):
    warnings = []
    resolved_messages = _canonicalize_messages(messages)
    if profile.system_prompt_mode == "user_injection":
        resolved_messages = _apply_user_injection(resolved_messages)
    reasoning_hint = None
    resolved_messages, reasoning_hint = _apply_reasoning_suppression_hint(
        resolved_messages,
        provider_backend=provider_backend,
        model=model,
        task_class=task_class,
        profile_id=profile.profile_id,
        allows_thinking_blocks=bool(profile.allows_thinking_blocks),
    )
    if profile.profile_id == "openai_compat.gemma.openai_messages.v1":
        already_compacted = is_compact_turn_packet(resolved_messages)
        if task_class == "tool_call" and not already_compacted:
            gemma_compaction = compact_turn_messages(
                resolved_messages,
                runtime_context=context,
            )
            resolved_messages = gemma_compaction.messages
            if gemma_compaction.applied:
                warnings.append(
                    "message_packet_compacted:gemma_tool_turn_v1:"
                    f"{gemma_compaction.source_message_count}->{gemma_compaction.compacted_message_count}"
                )
    resolved_messages, budget_warnings, effective_context_budget_tokens, context_budget_warning = _apply_budget(
        resolved_messages, context, profile, task_class, mode)
    warnings.extend(budget_warnings)
    if reasoning_hint:
        warnings.append(f"reasoning_suppression:{reasoning_hint}")
    if context_budget_warning:
        warnings.append(context_budget_warning)
    if lmstudio_session_mode in {"context", "fixed"} and not lmstudio_session_id:
        warnings.append("lmstudio_session_id_missing")
    if profile.profile_id == "openai_compat.gemma.openai_messages.v1":
        resolved_messages, collapsed_user_messages = _collapse_adjacent_user_messages(resolved_messages)
        if collapsed_user_messages > 0:
            warnings.append(f"message_shape:user_blocks_collapsed:{collapsed_user_messages}")
    return resolved_messages, warnings, effective_context_budget_tokens


def _apply_budget(resolved_messages, context, profile, task_class, mode):
    warnings = []
    effective_context_budget_tokens, context_budget_warning = _effective_context_budget_tokens(
        profile_id=profile.profile_id,
        task_class=task_class,
        runtime_context=context,
        profile_budget_tokens=int(profile.context_budget_tokens),
    )
    pretrim_messages = list(resolved_messages)
    resolved_messages, trimmed_count = _trim_messages_by_budget(
        pretrim_messages,
        context_budget_tokens=effective_context_budget_tokens,
    )
    if trimmed_count > 0:
        stripped_messages, stripped_history_count = _strip_prior_transcript_messages(pretrim_messages)
        if stripped_history_count > 0:
            stripped_messages, retrimmed_count = _trim_messages_by_budget(
                stripped_messages,
                context_budget_tokens=effective_context_budget_tokens,
            )
            if retrimmed_count <= trimmed_count:
                resolved_messages = stripped_messages
                trimmed_count = retrimmed_count
                warnings.append(f"context_history_stripped:{stripped_history_count}")
    role_violation = _role_forbidden_error(resolved_messages, profile)
    if role_violation:
        tool_path = task_class == "tool_call"
        if mode == "enforce" or (mode == "compat" and tool_path):
            raise ValueError(f"{E_LOCAL_PROMPT_ROLE_FORBIDDEN}:{role_violation}")
    if trimmed_count > 0:
        warnings.append(f"context_trimmed:{trimmed_count}")
    return resolved_messages, warnings, effective_context_budget_tokens, context_budget_warning


def _resolved_policy(resolved, resolved_messages, warnings, effective_context_budget_tokens,
    provider_backend, provider_for_profile, mode, task_class, requested_stops, requested_sampling,
    lmstudio_session_mode, lmstudio_session_id, registry_hash):
    effective_stops = _effective_stops(provider_backend, resolved.profile, task_class)
    effective_stops = list(dict.fromkeys(requested_stops + effective_stops))
    sampling_bundle = cap_sampling_bundle(_sampling_bundle(resolved.profile, task_class), requested_sampling)
    render_classification = _render_observability_classification(
        provider=provider_for_profile,
        profile=resolved.profile,
    )
    if render_classification == "message_payload_audited":
        template_hash, template_hash_alg, byte_count = "", "", 0
    else:
        template_hash, byte_count = _render_hash(resolved_messages)
        template_hash_alg = "sha256"
    return LocalPromptingPolicyResult(
        provider=provider_for_profile,
        mode=mode,
        task_class=task_class,
        messages=resolved_messages,
        profile_id=resolved.profile.profile_id,
        template_family=resolved.profile.template_family,
        template_version=resolved.profile.template_version,
        template_hash=template_hash,
        template_hash_alg=template_hash_alg,
        rendered_prompt_byte_count=byte_count,
        render_observability_classification=render_classification,
        stop_sequences_by_task_class=dict(resolved.profile.stop_sequences_by_task_class),
        effective_stop_sequences=effective_stops,
        sampling_bundle=sampling_bundle,
        tool_call_mode=str(resolved.profile.tool_call_mode),
        history_policy=str(resolved.profile.history_policy),
        allows_thinking_blocks=bool(resolved.profile.allows_thinking_blocks),
        thinking_block_format=str(resolved.profile.thinking_block_format),
        intro_phrase_denylist=list(resolved.profile.intro_phrase_denylist),
        lmstudio_session_mode=lmstudio_session_mode,
        lmstudio_session_id=lmstudio_session_id,
        resolution_path=resolved.resolution_path,
        profile_registry_snapshot_hash=registry_hash,
        warnings=warnings,
        context_budget_tokens=effective_context_budget_tokens,
    )
