from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_corrective_prompt import CorrectivePromptBuilder


def test_corrective_prompt_builder_includes_required_path_contracts(tmp_path: Path) -> None:
    required = tmp_path / "docs" / "spec.md"
    required.parent.mkdir(parents=True, exist_ok=True)
    required.write_text("spec", encoding="utf-8")
    builder = CorrectivePromptBuilder(tmp_path)
    prompt = builder.build_corrective_instruction(
        [{"reason": "read_path_contract_not_met"}, {"reason": "write_path_contract_not_met"}],
        {"required_read_paths": ["docs/spec.md"], "required_write_paths": ["agent_output/out.txt"]},
    )
    assert "Required read_file paths" in prompt
    assert "docs/spec.md" in prompt
    assert "Required write_file paths" in prompt
    assert "agent_output/out.txt" in prompt


def test_corrective_prompt_builder_failure_message_mapping() -> None:
    assert (
        CorrectivePromptBuilder.deterministic_failure_message("progress_contract_not_met")
        == "Deterministic failure: progress contract not met after corrective reprompt."
    )
