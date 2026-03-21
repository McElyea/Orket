from __future__ import annotations

import pytest

from orket.adapters.llm.openai_compat_runtime import extract_openai_content

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
