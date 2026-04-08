from __future__ import annotations

import warnings

import pytest

from orket.adapters.llm.local_prompting_policy import (
    E_LOCAL_PROMPT_PROFILE_REQUIRED,
    E_LOCAL_PROMPT_ROLE_FORBIDDEN,
    resolve_local_prompting_policy,
)

_QWEN_INTRO_DENYLIST = ["sure", "here is", "here's", "i will", "i'll", "thinking process:", "let me"]


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
    assert result.intro_phrase_denylist == _QWEN_INTRO_DENYLIST
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
    assert result.sampling_bundle["max_output_tokens"] == 2048
    assert result.intro_phrase_denylist == _QWEN_INTRO_DENYLIST


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
async def test_resolve_local_prompting_policy_selects_gemma_profile_for_openai_compat_tool_turns() -> None:
    """Layer: contract. Verifies strict LM Studio Gemma tool turns fail closed on a real profile, not fallback drift."""

    result = await resolve_local_prompting_policy(
        provider_backend="openai_compat",
        model="google/gemma-4-26b-a4b",
        messages=[{"role": "user", "content": "Write the required artifact and update status."}],
        runtime_context={
            "local_prompt_task_class": "tool_call",
            "local_prompting_mode": "enforce",
        },
    )

    assert result.profile_id == "openai_compat.gemma.openai_messages.v1"
    assert result.task_class == "tool_call"
    assert result.sampling_bundle["seed_policy"] == "fixed"
    assert result.sampling_bundle["seed_value"] == 71
    assert result.effective_stop_sequences == ["<|tool_end|>", "</s>"]
    assert result.intro_phrase_denylist == []


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_collapses_adjacent_user_blocks_for_gemma() -> None:
    result = await resolve_local_prompting_policy(
        provider_backend="openai_compat",
        model="google/gemma-4-26b-a4b",
        messages=[
            {"role": "system", "content": "You are the guard."},
            {"role": "user", "content": "Issue CWR-01"},
            {"role": "user", "content": "Execution Context JSON:\n{}"},
            {"role": "user", "content": "Turn Success Contract:\n- Required tool calls this turn: update_issue_status"},
        ],
        runtime_context={
            "local_prompt_task_class": "tool_call",
            "local_prompting_mode": "enforce",
        },
    )

    assert [message["role"] for message in result.messages] == ["system", "user"]
    assert "MODE: compact governed tool turn" in result.messages[0]["content"]
    assert "ALLOWED TOOLS:" not in result.messages[0]["content"]
    assert "TURN PACKET:" in result.messages[1]["content"]
    assert "Issue CWR-01" in result.messages[1]["content"]
    assert "Execution Context JSON:\n{}" not in result.messages[1]["content"]
    assert "Guard Decision Contract:" not in result.messages[1]["content"]
    assert "message_packet_compacted:gemma_tool_turn_v1:4->2" in result.warnings


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_trims_gemma_before_collapsing_user_blocks() -> None:
    result = await resolve_local_prompting_policy(
        provider_backend="openai_compat",
        model="google/gemma-4-26b-a4b",
            messages=[
                {"role": "system", "content": "You are the coder."},
                {"role": "user", "content": "Issue CWR-03"},
                {"role": "user", "content": "Preloaded Read Context:\nPath: agent_output/requirements.txt\nContent:\n" + ("x" * 4000)},
                {"role": "user", "content": "Turn Success Contract:\n- Required tool calls this turn: write_file"},
                {"role": "user", "content": "Write Path Contract:\n- Required write_file paths this turn:\n  - agent_output/out.json"},
            ],
        runtime_context={
            "local_prompt_task_class": "tool_call",
            "local_prompting_mode": "enforce",
        },
    )

    assert [message["role"] for message in result.messages] == ["system", "user"]
    assert "Issue CWR-03" in result.messages[1]["content"]
    assert "TURN PACKET:" in result.messages[1]["content"]
    assert "Preloaded Read Context:" in result.messages[1]["content"]
    assert ("x" * 4000) in result.messages[1]["content"]
    assert "message_packet_compacted:gemma_tool_turn_v1:5->2" in result.warnings


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_caps_gemma_multi_write_turns_more_aggressively() -> None:
    messages = [
        {"role": "system", "content": "You are the coder."},
        {"role": "user", "content": "Issue CWR-03"},
        {"role": "user", "content": "Preloaded Read Context:\nPath: agent_output/requirements.txt\nContent:\n" + ("x" * 4000)},
        {"role": "user", "content": "Turn Success Contract:\n- Required tool calls this turn: write_file"},
        {"role": "user", "content": "Write Path Contract:\n- Required write_file paths this turn:\n  - agent_output/out.json"},
    ]

    single_write = await resolve_local_prompting_policy(
        provider_backend="openai_compat",
        model="google/gemma-4-26b-a4b",
        messages=messages,
        runtime_context={
            "local_prompt_task_class": "tool_call",
            "local_prompting_mode": "enforce",
            "required_write_paths": ["agent_output/out.json"],
        },
    )
    multi_write = await resolve_local_prompting_policy(
        provider_backend="openai_compat",
        model="google/gemma-4-26b-a4b",
        messages=messages,
        runtime_context={
            "local_prompt_task_class": "tool_call",
            "local_prompting_mode": "enforce",
            "required_write_paths": [
                "agent_output/out-1.json",
                "agent_output/out-2.json",
                "agent_output/out-3.json",
            ],
        },
    )

    assert "TURN PACKET:" in single_write.messages[1]["content"]
    assert "Preloaded Read Context:" in single_write.messages[1]["content"]
    assert ("x" * 4000) in single_write.messages[1]["content"]
    assert ("x" * 4000) in multi_write.messages[1]["content"]
    assert "context_budget_cap:gemma_multi_write:2400" not in single_write.warnings
    assert "context_budget_cap:gemma_multi_write:2400" in multi_write.warnings
    assert "TURN PACKET:" in multi_write.messages[1]["content"]
    assert "message_packet_compacted:gemma_tool_turn_v1:5->2" in multi_write.warnings


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
    assert result.intro_phrase_denylist == _QWEN_INTRO_DENYLIST
    assert result.sampling_bundle["max_output_tokens"] == 1536
    assert "reasoning_suppression:qwen_no_think_prompt_hint" in result.warnings


@pytest.mark.asyncio
async def test_resolve_local_prompting_policy_drops_prior_transcript_before_other_trimmed_context() -> None:
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Issue CWR-10: Validator and Planner Tests"},
        {"role": "user", "content": "Execution Context JSON:\n" + ("x" * 6000)},
        {"role": "user", "content": "Artifact Contract JSON:\n" + ("y" * 6000)},
        {"role": "user", "content": "Prior Transcript JSON:\n" + ("z" * 20000)},
        {"role": "user", "content": "Corrective instruction: previous response violated deterministic turn contracts.\n" + ("w" * 6000)},
    ]

    result = await resolve_local_prompting_policy(
        provider_backend="ollama",
        model="qwen2.5-coder:14b",
        messages=messages,
        runtime_context={
            "protocol_governed_enabled": False,
            "required_action_tools": ["write_file", "update_issue_status"],
        },
    )

    assert "context_history_stripped:1" in result.warnings
    assert all(not message["content"].startswith("Prior Transcript JSON:\n") for message in result.messages)
    assert any(message["content"].startswith("Execution Context JSON:\n") for message in result.messages)


def test_local_prompting_bool_parse_warns_on_unrecognized_token() -> None:
    """Layer: unit. Verifies local prompting boolean parsing fails closed and emits an explicit warning on invalid tokens."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert resolve_local_prompting_policy.__globals__["_parse_bool"]("maybe") is False

    assert any("Unrecognized boolean token" in str(item.message) for item in caught)
