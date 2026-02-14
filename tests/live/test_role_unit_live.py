from __future__ import annotations

import os

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
    assert "REQUIREMENTS_ACCEPTED" in text
    assert "hello world" in text.lower()


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
    assert "ARCHITECTURE_ACCEPTED" in text
    assert "components" in text.lower()


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
    assert "hello world" in text.lower()
    assert "print" in text.lower()


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
    assert "REVIEW_ACCEPTED" in text
    assert ("pass" in text.lower()) or ("approve" in text.lower())
