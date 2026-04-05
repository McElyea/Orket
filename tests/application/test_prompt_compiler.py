from __future__ import annotations

from orket.application.services.prompt_compiler import PromptCompiler
from orket.schema import DialectConfig, SkillConfig


def test_prompt_compiler_protocol_governed_uses_single_envelope_contract() -> None:
    """Layer: contract. Verifies governed prompt compiler uses the single-envelope JSON response contract."""
    skill = SkillConfig(
        name="requirements_analyst",
        intent="Write requirements",
        responsibilities=["Produce requirements"],
        tools=["write_file", "update_issue_status"],
    )
    dialect = DialectConfig(
        model_family="qwen",
        dsl_format="JSON",
        constraints=["Return JSON only"],
        hallucination_guard="No extra prose",
    )

    prompt = PromptCompiler.compile(skill, dialect, protocol_governed_enabled=True)

    assert 'Required response envelope: {"content":"","tool_calls":[{"tool":"<tool_name>","args":{"key":"value"}}]}' in prompt
    assert "Do not use markdown fences" in prompt
    assert "Emit executable tool-call JSON blocks only." not in prompt


def test_prompt_compiler_architect_requires_architecture_decision_json_artifact() -> None:
    """Layer: contract. Verifies legacy architect prompts state the architecture decision JSON artifact contract."""
    skill = SkillConfig(
        name="architect",
        intent="Write architecture",
        responsibilities=["Produce architecture"],
        tools=["write_file", "update_issue_status"],
    )
    dialect = DialectConfig(
        model_family="qwen",
        dsl_format="JSON",
        constraints=["Return JSON only"],
        hallucination_guard="No extra prose",
    )

    prompt = PromptCompiler.compile(skill, dialect, protocol_governed_enabled=False)

    assert "You MUST write architecture decision JSON using write_file(path='agent_output/design.txt', ...)." in prompt
    assert "That JSON MUST include recommendation, confidence, and evidence keys." in prompt
    assert (
        "evidence MUST include: estimated_domains, external_integrations, independent_scaling_needs, "
        "deployment_complexity, team_parallelism, operational_maturity."
    ) in prompt


def test_prompt_compiler_code_reviewer_requires_all_read_paths_in_same_response() -> None:
    """Layer: contract. Verifies legacy reviewer prompts require all listed read paths in the same response."""
    skill = SkillConfig(
        name="code_reviewer",
        intent="Review implementation",
        responsibilities=["Review implementation"],
        tools=["read_file", "update_issue_status"],
    )
    dialect = DialectConfig(
        model_family="qwen",
        dsl_format="JSON",
        constraints=["Return JSON only"],
        hallucination_guard="No extra prose",
    )

    prompt = PromptCompiler.compile(skill, dialect, protocol_governed_enabled=False)

    assert "You MUST read every path listed in the Read Path Contract with read_file(...) in this same response." in prompt
    assert "Do not stop after reading only a subset of required artifacts." in prompt


def test_prompt_compiler_legacy_tool_path_uses_compact_unfenced_json_contract() -> None:
    skill = SkillConfig(
        name="coder",
        intent="Write implementation",
        responsibilities=["Produce implementation"],
        tools=["write_file", "update_issue_status"],
    )
    dialect = DialectConfig(
        model_family="qwen",
        dsl_format="JSON",
        constraints=["Return JSON only"],
        hallucination_guard="No extra prose",
    )

    prompt = PromptCompiler.compile(skill, dialect, protocol_governed_enabled=False)

    assert "Emit executable JSON only." in prompt
    assert 'For a single tool call, emit one compact JSON object: {"tool":"<tool_name>","args":{"key":"value"}}' in prompt
    assert '{"content":"","tool_calls":[{"tool":"<tool_name>","args":{"key":"value"}}]}' in prompt
    assert "Do not use markdown fences, labels, or backticks around tool-call JSON." in prompt
    assert "Escape newline characters inside string values; the JSON must parse without repair." in prompt
    assert 'If more than one tool call is needed, use {"content":"","tool_calls":[...]}' in prompt
    assert "```json" not in prompt
