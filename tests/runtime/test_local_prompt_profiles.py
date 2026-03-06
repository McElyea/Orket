from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.runtime.local_prompt_profiles import (
    E_LOCAL_PROMPT_PROFILE_AMBIGUOUS,
    E_LOCAL_PROMPT_PROFILE_FALLBACK_MISSING,
    E_LOCAL_PROMPT_PROFILE_NOT_FOUND,
    E_LOCAL_PROMPT_PROFILE_OVERRIDE_MISSING,
    E_LOCAL_PROMPT_PROFILE_SCHEMA,
    load_local_prompt_profile_registry_file,
    load_local_prompt_profile_registry_payload,
)


def _base_profile(profile_id: str) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "template_family": "openai_messages",
        "template_variant": "openai_chat",
        "template_source": "runtime_metadata",
        "template_version": "test_v1",
        "allowed_roles": ["system", "user", "assistant", "tool"],
        "system_prompt_mode": "native",
        "context_budget_tokens": 2048,
        "history_policy": "bounded_head_tail_v1",
        "stop_sequences_by_task_class": {
            "strict_json": ["<|json_end|>"],
            "tool_call": ["<|tool_end|>"],
            "concise_text": ["</s>"],
            "reasoning": ["</s>"],
        },
        "supports_assistant_prefill": False,
        "prefill_strategy": "none",
        "tool_call_mode": "native",
        "tool_contract": {
            "tool_manifest_injection": "system",
            "tool_call_schema": "tool_call.v1",
            "tool_result_role": "tool",
        },
        "allows_thinking_blocks": False,
        "thinking_block_format": "none",
        "sampling_bundles": {
            "strict_json": {
                "temperature": 0.0,
                "top_p": 1.0,
                "top_k": 1,
                "repeat_penalty": 1.0,
                "max_output_tokens": 128,
                "seed_policy": "fixed",
                "seed_value": 7,
            },
            "tool_call": {
                "temperature": 0.0,
                "top_p": 1.0,
                "top_k": 1,
                "repeat_penalty": 1.0,
                "max_output_tokens": 128,
                "seed_policy": "fixed",
                "seed_value": 11,
            },
            "concise_text": {
                "temperature": 0.2,
                "top_p": 0.9,
                "top_k": 20,
                "repeat_penalty": 1.0,
                "max_output_tokens": 256,
                "seed_policy": "provider_default",
            },
            "reasoning": {
                "temperature": 0.6,
                "top_p": 0.95,
                "top_k": 40,
                "repeat_penalty": 1.0,
                "max_output_tokens": 512,
                "seed_policy": "provider_default",
            },
        },
    }


def _payload(entries: list[dict[str, object]]) -> dict[str, object]:
    return {"schema_version": "local_prompt_profiles.v1", "profiles": entries}


def test_load_registry_file_defaults_to_repo_contract() -> None:
    registry = load_local_prompt_profile_registry_file()
    assert registry.schema_version == "local_prompt_profiles.v1"
    assert len(registry.profiles) >= 1


def test_resolve_profile_by_provider_and_model() -> None:
    registry = load_local_prompt_profile_registry_payload(
        _payload(
            [
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["qwen"]},
                    "profile": _base_profile("ollama.qwen.v1"),
                }
            ]
        )
    )

    resolved = registry.resolve_profile(provider="ollama", model="qwen2.5-coder:14b")
    assert resolved.profile.profile_id == "ollama.qwen.v1"
    assert resolved.resolution_path == "matched"


def test_resolve_profile_normalizes_lmstudio_provider_alias() -> None:
    registry = load_local_prompt_profile_registry_payload(
        _payload(
            [
                {
                    "provider": "openai_compat",
                    "match": {"model_contains": ["qwen"]},
                    "profile": _base_profile("openai_compat.qwen.v1"),
                }
            ]
        )
    )

    resolved = registry.resolve_profile(provider="lmstudio", model="qwen3.5-4b")
    assert resolved.provider == "openai_compat"
    assert resolved.profile.profile_id == "openai_compat.qwen.v1"


def test_resolve_profile_fail_closed_when_no_match() -> None:
    registry = load_local_prompt_profile_registry_payload(
        _payload(
            [
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["qwen"]},
                    "profile": _base_profile("ollama.qwen.v1"),
                }
            ]
        )
    )

    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_NOT_FOUND):
        registry.resolve_profile(provider="ollama", model="llama3.1:8b")


def test_resolve_profile_uses_explicit_fallback_when_allowed() -> None:
    registry = load_local_prompt_profile_registry_payload(
        _payload(
            [
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["qwen"]},
                    "profile": _base_profile("ollama.qwen.v1"),
                },
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["fallback"]},
                    "profile": _base_profile("ollama.fallback.v1"),
                },
            ]
        )
    )

    resolved = registry.resolve_profile(
        provider="ollama",
        model="llama3.1:8b",
        allow_fallback=True,
        fallback_profile_id="ollama.fallback.v1",
    )
    assert resolved.profile.profile_id == "ollama.fallback.v1"
    assert resolved.resolution_path == "fallback"


def test_resolve_profile_rejects_missing_override() -> None:
    registry = load_local_prompt_profile_registry_payload(
        _payload(
            [
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["qwen"]},
                    "profile": _base_profile("ollama.qwen.v1"),
                }
            ]
        )
    )

    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_OVERRIDE_MISSING):
        registry.resolve_profile(provider="ollama", model="qwen2.5-coder:14b", override_profile_id="missing.v1")


def test_resolve_profile_rejects_missing_fallback_profile() -> None:
    registry = load_local_prompt_profile_registry_payload(
        _payload(
            [
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["qwen"]},
                    "profile": _base_profile("ollama.qwen.v1"),
                }
            ]
        )
    )

    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_FALLBACK_MISSING):
        registry.resolve_profile(
            provider="ollama",
            model="llama3.1:8b",
            allow_fallback=True,
            fallback_profile_id="missing.fallback.v1",
        )


def test_resolve_profile_rejects_ambiguous_matches() -> None:
    registry = load_local_prompt_profile_registry_payload(
        _payload(
            [
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["qwen"]},
                    "profile": _base_profile("ollama.qwen.primary.v1"),
                },
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["qwen"]},
                    "profile": _base_profile("ollama.qwen.secondary.v1"),
                },
            ]
        )
    )

    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_AMBIGUOUS):
        registry.resolve_profile(provider="ollama", model="qwen2.5-coder:14b")


def test_registry_schema_rejects_missing_required_task_class() -> None:
    profile = _base_profile("ollama.qwen.v1")
    sampling_bundles = dict(profile["sampling_bundles"])
    sampling_bundles.pop("reasoning")
    profile["sampling_bundles"] = sampling_bundles

    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_SCHEMA):
        load_local_prompt_profile_registry_payload(
            _payload(
                [
                    {
                        "provider": "ollama",
                        "match": {"model_contains": ["qwen"]},
                        "profile": profile,
                    }
                ]
            )
        )


def test_registry_normalizes_intro_phrase_denylist_tokens() -> None:
    profile = _base_profile("ollama.qwen.v1")
    profile["intro_phrase_denylist"] = ["Sure", "  Here is ", "sure", ""]
    registry = load_local_prompt_profile_registry_payload(
        _payload(
            [
                {
                    "provider": "ollama",
                    "match": {"model_contains": ["qwen"]},
                    "profile": profile,
                }
            ]
        )
    )
    resolved = registry.resolve_profile(provider="ollama", model="qwen2.5-coder:14b")
    assert resolved.profile.intro_phrase_denylist == ["sure", "here is"]


def test_registry_file_load_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text("{not-json}", encoding="utf-8")
    with pytest.raises(ValueError, match="E_LOCAL_PROMPT_PROFILE_LOAD"):
        load_local_prompt_profile_registry_file(path)


def test_registry_file_load_rejects_non_object_root(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(["bad"]), encoding="utf-8")
    with pytest.raises(ValueError, match="E_LOCAL_PROMPT_PROFILE_LOAD"):
        load_local_prompt_profile_registry_file(path)
