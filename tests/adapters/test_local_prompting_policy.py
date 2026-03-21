from __future__ import annotations

import pytest

from orket.adapters.llm.local_prompting_policy import (
    E_LOCAL_PROMPT_PROFILE_REQUIRED,
    E_LOCAL_PROMPT_ROLE_FORBIDDEN,
    resolve_local_prompting_policy,
)


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_selects_matching_profile_for_ollama_qwen() -> None:
    result = await resolve_local_prompting_policy(
        provider_backend="ollama",
        model="qwen2.5-coder:14b",
        messages=[{"role": "user", "content": "hello"}],
        runtime_context={"protocol_governed_enabled": True},
    )
    assert result.profile_id == "ollama.qwen.chatml.v1"
    assert result.task_class == "strict_json"
    assert result.template_hash_alg == "sha256"
    assert result.rendered_prompt_byte_count > 0
    assert result.effective_stop_sequences
    assert result.sampling_bundle["max_output_tokens"] > 0
    assert result.intro_phrase_denylist == []
    assert result.thinking_block_format == "none"
    assert result.lmstudio_session_mode == "none"
    assert result.lmstudio_session_id == ""


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_applies_user_injection_for_deepseek_profile() -> None:
    result = await resolve_local_prompting_policy(
        provider_backend="ollama",
        model="deepseek-r1:14b",
        messages=[
            {"role": "system", "content": "system rule"},
            {"role": "user", "content": "question"},
        ],
        runtime_context={"protocol_governed_enabled": True},
    )
    assert result.profile_id == "ollama.deepseek_r1.custom.v1"
    assert result.messages[0]["role"] == "user"
    assert "[SYSTEM_INSTRUCTION_BEGIN]" in result.messages[0]["content"]


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_fails_closed_for_strict_missing_profile() -> None:
    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_REQUIRED):
        await resolve_local_prompting_policy(
            provider_backend="ollama",
            model="unknown-model-family",
            messages=[{"role": "user", "content": "hello"}],
            runtime_context={"protocol_governed_enabled": True, "local_prompting_mode": "enforce"},
        )


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_shadow_mode_allows_unresolved_profile() -> None:
    result = await resolve_local_prompting_policy(
        provider_backend="ollama",
        model="unknown-model-family",
        messages=[{"role": "user", "content": "hello"}],
        runtime_context={"protocol_governed_enabled": False, "local_prompting_mode": "shadow"},
    )
    assert result.profile_id == "unresolved"
    assert result.resolution_path == "unresolved"
    assert result.warnings


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_rejects_forbidden_role_on_tool_path() -> None:
    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_ROLE_FORBIDDEN):
        await resolve_local_prompting_policy(
            provider_backend="openai_compat",
            model="qwen3.5-4b",
            messages=[
                {"role": "coder", "content": "invalid role"},
                {"role": "user", "content": "hello"},
            ],
            runtime_context={"local_prompt_task_class": "tool_call", "local_prompting_mode": "compat"},
        )


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_uses_tool_call_bundle_when_required_tools_exist_without_protocol_governance() -> None:
    """Layer: contract. Verifies required tool turns stay on deterministic tool_call sampling without protocol mode."""

    result = await resolve_local_prompting_policy(
        provider_backend="ollama",
        model="qwen2.5-coder:7b",
        messages=[{"role": "user", "content": "hello"}],
        runtime_context={
            "protocol_governed_enabled": False,
            "required_action_tools": ["write_file", "update_issue_status"],
        },
    )

    assert result.task_class == "tool_call"
    assert result.sampling_bundle["temperature"] == 0.0
    assert result.sampling_bundle["seed_policy"] == "fixed"
    assert result.sampling_bundle["seed_value"] == 17


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_lmstudio_fixed_session_injects_payload_override() -> None:
    result = await resolve_local_prompting_policy(
        provider_backend="openai_compat",
        model="qwen3.5-4b",
        messages=[{"role": "user", "content": "hello"}],
        runtime_context={
            "protocol_governed_enabled": True,
            "lmstudio_session_mode": "fixed",
            "lmstudio_session_id": "session-fixed-001",
        },
    )
    overrides = result.openai_payload_overrides()
    assert result.lmstudio_session_mode == "fixed"
    assert result.lmstudio_session_id == "session-fixed-001"
    assert overrides["session_id"] == "session-fixed-001"


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_lmstudio_context_session_uses_runtime_session_id() -> None:
    result = await resolve_local_prompting_policy(
        provider_backend="openai_compat",
        model="qwen3.5-4b",
        messages=[{"role": "user", "content": "hello"}],
        runtime_context={
            "protocol_governed_enabled": True,
            "lmstudio_session_mode": "context",
            "session_id": "run-session-42",
        },
    )
    assert result.lmstudio_session_mode == "context"
    assert result.lmstudio_session_id == "run-session-42"
    telemetry = result.telemetry()
    assert telemetry["lmstudio_session_mode"] == "context"
    assert telemetry["lmstudio_session_id_present"] is True


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_adds_qwen_no_think_hint_for_openai_compat_non_reasoning() -> None:
    result = await resolve_local_prompting_policy(
        provider_backend="openai_compat",
        model="qwen/qwen3.5-35b-a3b",
        messages=[{"role": "user", "content": "Return the required four sections only."}],
        runtime_context={"local_prompt_task_class": "concise_text"},
    )

    assert result.profile_id == "openai_compat.qwen.openai_messages.v1"
    assert result.messages[-1]["content"].endswith("/no_think")
    assert result.sampling_bundle["max_output_tokens"] == 1536
    assert "reasoning_suppression:qwen_no_think_prompt_hint" in result.warnings
