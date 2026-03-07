from __future__ import annotations

from pathlib import Path

import pytest

from orket.runtime.prompt_budget_policy import load_prompt_budget_policy, resolve_prompt_stage


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Layer: unit
def test_load_prompt_budget_policy_parses_valid_policy(tmp_path: Path) -> None:
    policy_path = tmp_path / "core" / "policies" / "prompt_budget.yaml"
    _write(
        policy_path,
        """
schema_version: "1.0"
budget_policy_version: "1.0"
stages:
  planner:
    max_tokens: 1000
    protocol_tokens: 400
    tool_schema_tokens: 400
    task_tokens: 400
  executor:
    max_tokens: 1200
    protocol_tokens: 400
    tool_schema_tokens: 400
    task_tokens: 500
  reviewer:
    max_tokens: 900
    protocol_tokens: 300
    tool_schema_tokens: 300
    task_tokens: 300
""".strip()
        + "\n",
    )

    policy = load_prompt_budget_policy(policy_path)
    assert policy["schema_version"] == "1.0"
    assert policy["budget_policy_version"] == "1.0"
    assert policy["stages"]["executor"]["max_tokens"] == 1200


# Layer: contract
def test_load_prompt_budget_policy_fails_closed_on_missing_stage(tmp_path: Path) -> None:
    policy_path = tmp_path / "core" / "policies" / "prompt_budget.yaml"
    _write(
        policy_path,
        """
schema_version: "1.0"
budget_policy_version: "1.0"
stages:
  planner:
    max_tokens: 1000
    protocol_tokens: 400
    tool_schema_tokens: 400
    task_tokens: 400
  executor:
    max_tokens: 1200
    protocol_tokens: 400
    tool_schema_tokens: 400
    task_tokens: 500
""".strip()
        + "\n",
    )

    with pytest.raises(ValueError, match="missing_stage:reviewer"):
        _ = load_prompt_budget_policy(policy_path)


# Layer: unit
def test_resolve_prompt_stage_defaults_by_role() -> None:
    assert resolve_prompt_stage({"role": "architect"}) == "planner"
    assert resolve_prompt_stage({"role": "coder"}) == "executor"
    assert resolve_prompt_stage({"role": "code_reviewer"}) == "reviewer"
    assert resolve_prompt_stage({"role": "unknown"}) == "executor"
