"""Captured local prompt policy values and the application preparation port."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from orket.core.contracts.model_generation_options import sampling_payload


@dataclass(frozen=True)
class LocalPromptingPolicyResult:
    provider: str
    mode: str
    task_class: str
    messages: tuple[Mapping[str, str], ...]
    profile_id: str
    template_family: str
    template_version: str
    template_hash: str
    template_hash_alg: str
    rendered_prompt_byte_count: int
    render_observability_classification: str
    stop_sequences_by_task_class: Mapping[str, tuple[str, ...]]
    effective_stop_sequences: tuple[str, ...]
    sampling_bundle: Mapping[str, Any]
    tool_call_mode: str
    history_policy: str
    allows_thinking_blocks: bool
    thinking_block_format: str
    intro_phrase_denylist: tuple[str, ...]
    lmstudio_session_mode: str
    lmstudio_session_id: str
    resolution_path: str
    profile_registry_snapshot_hash: str
    warnings: tuple[str, ...]
    context_budget_tokens: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "messages", tuple(MappingProxyType(dict(row)) for row in self.messages))
        object.__setattr__(self, "stop_sequences_by_task_class", MappingProxyType(
            {key: tuple(values) for key, values in self.stop_sequences_by_task_class.items()}))
        object.__setattr__(self, "sampling_bundle", MappingProxyType(dict(self.sampling_bundle)))
        for name in ("effective_stop_sequences", "intro_phrase_denylist", "warnings"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    def message_payload(self) -> list[dict[str, str]]:
        return [dict(row) for row in self.messages]

    def openai_payload_overrides(self) -> dict[str, Any]:
        overrides = sampling_payload(self.sampling_bundle, ollama=False, extended=self.profile_id.startswith("llama_cpp."))
        if self.effective_stop_sequences:
            overrides["stop"] = list(self.effective_stop_sequences)
        if self.lmstudio_session_mode != "none" and self.lmstudio_session_id:
            overrides["session_id"] = self.lmstudio_session_id
        return overrides

    def ollama_options_overrides(self) -> dict[str, Any]:
        overrides = sampling_payload(self.sampling_bundle, ollama=True, extended=True)
        if self.effective_stop_sequences:
            overrides["stop"] = list(self.effective_stop_sequences)
        return overrides

    def telemetry(self) -> dict[str, Any]:
        return {
            "local_prompt_provider": self.provider,
            "local_prompting_mode": self.mode,
            "task_class": self.task_class,
            "profile_id": self.profile_id,
            "template_family": self.template_family,
            "template_version": self.template_version,
            "template_hash": self.template_hash,
            "template_hash_alg": self.template_hash_alg,
            "rendered_prompt_byte_count": self.rendered_prompt_byte_count,
            "render_observability_classification": self.render_observability_classification,
            "sampling_bundle": dict(self.sampling_bundle),
            "stop_sequences_by_task_class": {key: list(values) for key, values in self.stop_sequences_by_task_class.items()},
            "effective_stop_sequences": list(self.effective_stop_sequences),
            "tool_call_mode": self.tool_call_mode,
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


class LocalPromptingPort(Protocol):
    async def resolve(self, *, provider_backend: str, model: str, messages: list[dict[str, str]],
                      profile_provider: str | None = None,
                      runtime_context: dict[str, Any] | None = None) -> LocalPromptingPolicyResult: ...
