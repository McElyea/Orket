from __future__ import annotations

import os
from typing import Dict, List

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider


def _live_enabled() -> bool:
    return os.getenv("ORKET_LIVE_ROLE_TESTS", "").strip().lower() in {"1", "true", "yes"}


def _model_name() -> str:
    return os.getenv("ORKET_LIVE_MODEL", "qwen2.5-coder:7b")


def _seed_value() -> int:
    raw = os.getenv("ORKET_LIVE_SEED", "7").strip()
    try:
        return int(raw)
    except ValueError:
        return 7


ROLE_ACCEPTANCE: Dict[str, Dict[str, List[str]]] = {
    "requirements_analyst": {
        "required_tokens": ["REQUIREMENTS_ACCEPTED"],
        "required_all_substrings": ["hello world"],
        "required_any_substrings": [],
    },
    "architect": {
        "required_tokens": ["ARCHITECTURE_ACCEPTED"],
        "required_all_substrings": ["components"],
        "required_any_substrings": [],
    },
    "coder": {
        "required_tokens": [],
        "required_all_substrings": ["hello world", "print"],
        "required_any_substrings": [],
    },
    "code_reviewer": {
        "required_tokens": ["REVIEW_ACCEPTED"],
        "required_all_substrings": [],
        "required_any_substrings": ["pass", "approve", "review_accepted"],
    },
}


def _contains_all(haystack: str, needles: List[str]) -> bool:
    return all(needle in haystack for needle in needles)


def _assert_role_output(role: str, text: str) -> None:
    cfg = ROLE_ACCEPTANCE[role]
    normalized = (text or "").strip()
    normalized_lower = normalized.lower()

    if role == "architect":
        token_ok = "ARCHITECTURE_ACCEPTED" in normalized
        structure_ok = _contains_all(normalized_lower, ["components", "flow"])
        assert token_ok or structure_ok, (
            "architect: expected ARCHITECTURE_ACCEPTED token or structural sections "
            "('components' and 'flow')"
        )
    else:
        for token in cfg["required_tokens"]:
            assert token in normalized, f"{role}: missing required token '{token}'"

    for expected in cfg["required_all_substrings"]:
        assert expected in normalized_lower, f"{role}: missing expected substring '{expected}'"
    if cfg["required_any_substrings"]:
        assert any(expected in normalized_lower for expected in cfg["required_any_substrings"]), (
            f"{role}: none of accepted substrings present {cfg['required_any_substrings']}"
        )


async def _complete_for_role(system_prompt: str, task: str) -> str:
    provider = LocalModelProvider(
        model=_model_name(),
        temperature=0.0,
        seed=_seed_value(),
        timeout=300,
    )
    response = await provider.complete(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]
    )
    return response.content or ""


@pytest.mark.asyncio
async def test_live_role_requirements_analyst_unit():
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ROLE_TESTS=1 to run live per-role deterministic checks.")

    text = await _complete_for_role(
        system_prompt=(
            "You are a requirements_analyst. "
            "Output plain text only. Include the exact token REQUIREMENTS_ACCEPTED once."
        ),
        task=(
            "Task: define requirements for a tiny CLI app that prints Hello World. "
            "Must include a bullet for input and output."
        ),
    )
    print(f"[role-unit][requirements_analyst] {text[:200]}")
    _assert_role_output("requirements_analyst", text)


@pytest.mark.asyncio
async def test_live_role_architect_unit():
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ROLE_TESTS=1 to run live per-role deterministic checks.")

    text = await _complete_for_role(
        system_prompt=(
            "You are an architect. "
            "Output plain text only. Include the exact token ARCHITECTURE_ACCEPTED once."
        ),
        task=(
            "Task: produce a minimal architecture for a tiny CLI app that prints Hello World. "
            "Use sections: Components, Flow."
        ),
    )
    print(f"[role-unit][architect] {text[:200]}")
    _assert_role_output("architect", text)


@pytest.mark.asyncio
async def test_live_role_coder_unit_contains_hello_world():
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ROLE_TESTS=1 to run live per-role deterministic checks.")

    text = await _complete_for_role(
        system_prompt=(
            "You are a coder. "
            "Output Python code only. Include a line that prints Hello World exactly."
        ),
        task=(
            "Task: write the smallest runnable Python program for this behavior."
        ),
    )
    print(f"[role-unit][coder] {text[:200]}")
    _assert_role_output("coder", text)


@pytest.mark.asyncio
async def test_live_role_code_reviewer_unit():
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ROLE_TESTS=1 to run live per-role deterministic checks.")

    text = await _complete_for_role(
        system_prompt=(
            "You are a code_reviewer. "
            "Output plain text only. Include the exact token REVIEW_ACCEPTED once."
        ),
        task=(
            "Task: review this snippet and decide pass or fail:\n"
            "```python\nprint('Hello World')\n```"
        ),
    )
    print(f"[role-unit][code_reviewer] {text[:200]}")
    _assert_role_output("code_reviewer", text)
