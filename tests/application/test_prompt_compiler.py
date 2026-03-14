from __future__ import annotations

from orket.application.services.prompt_compiler import PromptCompiler
from orket.schema import DialectConfig, SkillConfig


def test_prompt_compiler_protocol_governed_uses_single_envelope_contract() -> None:
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
