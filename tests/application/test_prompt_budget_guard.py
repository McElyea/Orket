from __future__ import annotations

from pathlib import Path

import pytest

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
    _policy(policy_path, max_tokens=5000)
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
    _policy(policy_path, max_tokens=10)
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
    _policy(policy_path, max_tokens=5000)
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
