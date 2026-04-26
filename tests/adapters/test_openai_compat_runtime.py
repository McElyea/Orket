from __future__ import annotations

import pytest

from orket.adapters.llm.openai_compat_runtime import (
    build_orket_session_id,
    extract_openai_content,
    extract_openai_usage,
    validate_openai_messages,
)

pytestmark = pytest.mark.unit


def test_extract_openai_content_prefers_message_content_over_reasoning_content() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "### REQUIREMENT\nVisible answer",
                    "reasoning_content": "hidden reasoning fallback",
                }
            }
        ]
    }

    assert extract_openai_content(payload) == "### REQUIREMENT\nVisible answer"


def test_extract_openai_content_falls_back_to_reasoning_content_when_content_is_empty() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": "### REQUIREMENT\nFallback answer",
                }
            }
        ]
    }

    assert extract_openai_content(payload) == "### REQUIREMENT\nFallback answer"


def test_extract_openai_content_recovers_architect_sections_from_reasoning_tail() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": (
                        "Thinking Process:\n\n"
                        "1. Analyze the request.\n\n"
                        "Let's assemble.\n\n"
                        "*Requirement:* Store profile data locally for 30 days.\n\n"
                        "*Changelog:* Added the seeded retention policy.\n\n"
                        "*Assumptions:* The device provides persistent local storage.\n\n"
                        "*Open Questions:* None.\n\n"
                        "Wait, I need to double-check the wording."
                    ),
                }
            }
        ]
    }

    assert extract_openai_content(payload) == (
        "### REQUIREMENT\n"
        "Store profile data locally for 30 days.\n\n"
        "### CHANGELOG\n"
        "Added the seeded retention policy.\n\n"
        "### ASSUMPTIONS\n"
        "The device provides persistent local storage.\n\n"
        "### OPEN_QUESTIONS\n"
        "None."
    )


def test_extract_openai_content_recovers_auditor_sections_from_reasoning_tail() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": (
                        "Thinking Process:\n\n"
                        "Let's assemble.\n\n"
                        "*Critique:* The requirement still lacks a retention limit.\n\n"
                        "*Patches:* [REWRITE] Add a 30 day retention clause.\n\n"
                        "*Edge Cases:* Local disk full during retention rollover.\n\n"
                        "*Test Gaps:* No test covers retention expiry.\n\n"
                        "Let's finalize the response."
                    ),
                }
            }
        ]
    }

    assert extract_openai_content(payload) == (
        "### CRITIQUE\n"
        "The requirement still lacks a retention limit.\n\n"
        "### PATCHES\n"
        "[REWRITE] Add a 30 day retention clause.\n\n"
        "### EDGE_CASES\n"
        "Local disk full during retention rollover.\n\n"
        "### TEST_GAPS\n"
        "No test covers retention expiry."
    )


def test_extract_openai_content_recovers_direct_header_block_and_trims_numbered_meta_tail() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": (
                        "Thinking Process:\n\n"
                        "### REQUIREMENT\n"
                        "Store data locally.\n\n"
                        "### CHANGELOG\n"
                        "Added a local-only constraint.\n\n"
                        "### ASSUMPTIONS\n"
                        "The device has writable storage.\n\n"
                        "### OPEN_QUESTIONS\n"
                        "None.\n\n"
                        "6.  **Final Check:**\n"
                        "    *   Four sections exactly? Yes.\n\n"
                        "*Self-Correction on wording:* keep it concise."
                    ),
                }
            }
        ]
    }

    assert extract_openai_content(payload) == (
        "### REQUIREMENT\n"
        "Store data locally.\n\n"
        "### CHANGELOG\n"
        "Added a local-only constraint.\n\n"
        "### ASSUMPTIONS\n"
        "The device has writable storage.\n\n"
        "### OPEN_QUESTIONS\n"
        "None."
    )


def test_extract_openai_content_does_not_trim_adversarial_stop_marker_phrases() -> None:
    """Layer: unit. Verifies ordinary content does not match reasoning-tail stop markers."""
    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": (
                        "### REQUIREMENT\n"
                        "Document formatting rules for operators.\n\n"
                        "### CHANGELOG\n"
                        "Added wait for lock guidance.\n\n"
                        "### ASSUMPTIONS\n"
                        "The team can wait for lock release.\n\n"
                        "### OPEN_QUESTIONS\n"
                        "Should we let's refactor this later?"
                    ),
                }
            }
        ]
    }

    assert extract_openai_content(payload) == (
        "### REQUIREMENT\n"
        "Document formatting rules for operators.\n\n"
        "### CHANGELOG\n"
        "Added wait for lock guidance.\n\n"
        "### ASSUMPTIONS\n"
        "The team can wait for lock release.\n\n"
        "### OPEN_QUESTIONS\n"
        "Should we let's refactor this later?"
    )


def test_extract_openai_content_returns_raw_reasoning_when_no_recoverable_sections_exist() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": "Thinking Process:\n1. Analyze the request.\n2. Draft a response.",
                }
            }
        ]
    }

    assert extract_openai_content(payload) == "Thinking Process:\n1. Analyze the request.\n2. Draft a response."


def test_extract_openai_content_returns_none_for_structural_failure() -> None:
    """Layer: unit. Verifies broken provider envelopes are distinguishable from empty model text."""
    assert extract_openai_content({}) is None
    assert extract_openai_content({"choices": []}) is None
    assert extract_openai_content({"choices": [{"delta": {"content": "stream fragment"}}]}) is None
    assert extract_openai_content({"choices": [{"message": {"content": [{"text": 7}]}}]}) is None


def test_extract_openai_content_allows_legitimate_empty_message() -> None:
    """Layer: unit. Verifies empty assistant text remains distinct from structural failure."""
    payload = {"choices": [{"message": {"role": "assistant", "content": "", "reasoning_content": ""}}]}

    assert extract_openai_content(payload) == ""


def test_extract_openai_usage_accepts_negative_integer_strings() -> None:
    """Layer: unit. Verifies integer parsing fails closed only for non-integer strings."""
    assert extract_openai_usage({"usage": {"prompt_tokens": "-2", "completion_tokens": "3"}}) == (-2, 3, 1)
    assert extract_openai_usage({"usage": {"prompt_tokens": "1.5", "completion_tokens": "3"}}) == (None, 3, None)


def test_build_orket_session_id_does_not_use_seat_id_as_session_authority() -> None:
    """Layer: unit. Verifies role/seat identifiers do not become provider session identifiers."""
    session_id = build_orket_session_id(
        runtime_context={"seat_id": "seat-42", "run_id": "run-42"},
        model="model-a",
        provider_name="provider-a",
        fallback_messages=[{"role": "user", "content": "hello"}],
    )

    assert session_id == "run-42"


def test_build_orket_session_id_fallback_is_collision_resistant() -> None:
    """Layer: unit. Verifies identical prompts without explicit run context do not collide."""
    kwargs = {
        "runtime_context": {},
        "model": "model-a",
        "provider_name": "provider-a",
        "fallback_messages": [{"role": "user", "content": "hello"}],
    }

    first = build_orket_session_id(**kwargs)
    second = build_orket_session_id(**kwargs)

    assert first != second
    assert first.startswith("derived-")
    assert second.startswith("derived-")


def test_validate_openai_messages_reports_original_role_value() -> None:
    """Layer: unit. Verifies invalid-role diagnostics preserve the caller's original role token."""
    invalid = validate_openai_messages([{"role": "  Developer  "}, {"content": "missing"}])

    assert invalid == ["0:  Developer  ", "1:<missing>"]
