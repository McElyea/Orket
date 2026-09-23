from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.application.workflows import prompt_token_counter as token_counter
from orket.application.workflows.prompt_budget_guard import (
    build_prompt_structure_payload,
    evaluate_prompt_budget,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _policy(path: Path, *, max_tokens: int) -> None:
    _write(
        path,
        f"""
schema_version: "1.0"
budget_policy_version: "1.0"
stages:
  planner:
    max_tokens: {max_tokens}
    protocol_tokens: {max_tokens}
    tool_schema_tokens: {max_tokens}
    task_tokens: {max_tokens}
  executor:
    max_tokens: {max_tokens}
    protocol_tokens: {max_tokens}
    tool_schema_tokens: {max_tokens}
    task_tokens: {max_tokens}
  reviewer:
    max_tokens: {max_tokens}
    protocol_tokens: {max_tokens}
    tool_schema_tokens: {max_tokens}
    task_tokens: {max_tokens}
""".strip()
        + "\n",
    )


class _ModelWithTokenizer:
    async def count_tokens(self, messages):
        total_chars = sum(len(str((row or {}).get("content") or "")) for row in messages if isinstance(row, dict))
        return {"token_count": max(1, total_chars // 4), "tokenizer_id": "unit-test-tokenizer"}


# Layer: integration
@pytest.mark.asyncio
async def test_evaluate_prompt_budget_uses_backend_tokenizer_counter(tmp_path: Path) -> None:
    policy_path = tmp_path / "core" / "policies" / "prompt_budget.yaml"
    await asyncio.to_thread(_policy, policy_path, max_tokens=5000)
    messages = [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "Execution Context JSON:{}"},
        {"role": "user", "content": "Implement feature"},
    ]

    result = await evaluate_prompt_budget(
        messages=messages,
        context={
            "role": "coder",
            "prompt_budget_policy_path": str(policy_path),
            "prompt_budget_require_backend_tokenizer": True,
        },
        model_client=_ModelWithTokenizer(),
    )

    assert result["ok"] is True
    assert result["tokenizer_source"] == "backend"
    assert result["tokenizer_id"] == "unit-test-tokenizer"


# Layer: contract
@pytest.mark.asyncio
async def test_evaluate_prompt_budget_fails_closed_when_budget_exceeded(tmp_path: Path) -> None:
    policy_path = tmp_path / "core" / "policies" / "prompt_budget.yaml"
    await asyncio.to_thread(_policy, policy_path, max_tokens=10)
    messages = [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "Task " * 200},
    ]

    result = await evaluate_prompt_budget(
        messages=messages,
        context={
            "role": "coder",
            "prompt_budget_policy_path": str(policy_path),
            "prompt_budget_require_backend_tokenizer": False,
        },
        model_client=object(),
    )

    assert result["ok"] is False
    assert "E_PROMPT_BUDGET_EXCEEDED" in str(result["error"])


# Layer: contract
@pytest.mark.asyncio
async def test_evaluate_prompt_budget_fails_when_backend_tokenizer_required_but_unavailable(tmp_path: Path) -> None:
    policy_path = tmp_path / "core" / "policies" / "prompt_budget.yaml"
    await asyncio.to_thread(_policy, policy_path, max_tokens=5000)
    messages = [{"role": "user", "content": "Implement feature"}]

    result = await evaluate_prompt_budget(
        messages=messages,
        context={
            "role": "coder",
            "prompt_budget_policy_path": str(policy_path),
            "prompt_budget_require_backend_tokenizer": True,
        },
        model_client=object(),
    )

    assert result["ok"] is False
    assert "E_TOKENIZER_ACCOUNTING" in str(result["error"])


# Layer: unit
def test_build_prompt_structure_payload_captures_required_fields() -> None:
    payload = build_prompt_structure_payload(
        context={"prompt_metadata": {"prompt_version": "2026.03.06"}},
        prompt_hash="abc123",
        message_count=5,
        budget_result={
            "stage": "executor",
            "tokenizer_id": "tokenizer-x",
            "tokenizer_source": "backend",
            "budget_policy_version": "1.0",
        },
    )

    assert payload["prompt_template_version"] == "2026.03.06"
    assert payload["prompt_stage"] == "executor"
    assert payload["tokenizer_id"] == "tokenizer-x"


# Layer: unit
def test_counter_resolution_prefers_the_direct_client_binding() -> None:
    class Provider:
        def count_tokens(self, _messages):  # type: ignore[no-untyped-def]
            return 2

    class Client:
        provider = Provider()

        def count_tokens(self, _messages):  # type: ignore[no-untyped-def]
            return 1

    client = Client()
    selected = token_counter.resolve_token_counter(client)

    assert selected.__self__ is client
    assert selected([]) == 1


# Layer: contract
@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [ValueError, TypeError, RuntimeError, OSError, AttributeError])
async def test_recognized_callback_errors_keep_strict_and_nonstrict_results(error_type) -> None:
    def fail(_messages):  # type: ignore[no-untyped-def]
        raise error_type("controlled")

    strict = await token_counter._count_tokens(
        bucket="total", counter=fail, known_async_counter=False,
        messages=[{"role": "user", "content": "abcd"}], require_backend_tokenizer=True,
    )
    nonstrict = await token_counter._count_tokens(
        bucket="total", counter=fail, known_async_counter=False,
        messages=[{"role": "user", "content": "abcd"}], require_backend_tokenizer=False,
    )

    assert strict["error"] == "E_TOKENIZER_ACCOUNTING:backend_counter_error:controlled"
    assert nonstrict == {
        "token_count": 1,
        "tokenizer_id": "deterministic-fallback-v1",
        "tokenizer_source": "deterministic_fallback",
    }


# Layer: contract
@pytest.mark.asyncio
async def test_counter_normalization_failure_is_not_converted() -> None:
    class BrokenTokenizerId:
        def __str__(self) -> str:
            raise ValueError("normalization-failed")

    def count(_messages):  # type: ignore[no-untyped-def]
        return {"token_count": 1, "tokenizer_id": BrokenTokenizerId()}

    with pytest.raises(ValueError, match="normalization-failed"):
        await token_counter._count_tokens(
            bucket="total", counter=count, known_async_counter=False,
            messages=[{"role": "user", "content": "x"}], require_backend_tokenizer=False,
        )


# Layer: contract
@pytest.mark.asyncio
async def test_counter_does_not_await_noncoroutine_awaitable() -> None:
    class AwaitableValue:
        awaited = False

        def __await__(self):  # type: ignore[no-untyped-def]
            self.awaited = True
            yield
            return 4

    value = AwaitableValue()
    result = await token_counter._count_tokens(
        bucket="total", counter=lambda _messages: value, known_async_counter=False,
        messages=[{"role": "user", "content": "x"}], require_backend_tokenizer=True,
    )

    assert result["error"] == "E_TOKENIZER_ACCOUNTING:backend_counter_invalid_payload"
    assert value.awaited is False
