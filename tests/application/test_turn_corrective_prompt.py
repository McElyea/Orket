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


def test_corrective_prompt_builder_protocol_governed_uses_single_envelope_template(tmp_path: Path) -> None:
    builder = CorrectivePromptBuilder(tmp_path)
    prompt = builder.build_corrective_instruction(
        [{"reason": "progress_contract_not_met"}],
        {
            "protocol_governed_enabled": True,
            "required_action_tools": ["write_file", "update_issue_status"],
            "required_statuses": ["code_review"],
            "required_write_paths": ["agent_output/requirements.txt"],
        },
    )

    assert '"content": "", "tool_calls":' in prompt
    assert "do not use markdown fences" in prompt.lower()


def test_corrective_prompt_builder_includes_artifact_semantic_deltas(tmp_path: Path) -> None:
    builder = CorrectivePromptBuilder(tmp_path)
    prompt = builder.build_corrective_instruction(
        [
            {
                "reason": "artifact_semantic_contract_not_met",
                "violations": [
                    {
                        "path": "agent_output/challenge_runtime/simulator.py",
                        "label": "deterministic simulator",
                        "missing_tokens": ["for layer in layers", "self.run_task(task)"],
                        "forbidden_tokens": ["plan_workflow(self.workflow)"],
                    }
                ],
            }
        ],
        {
            "required_action_tools": ["write_file", "update_issue_status"],
            "required_statuses": ["code_review"],
            "required_write_paths": ["agent_output/challenge_runtime/simulator.py"],
        },
    )

    assert "Artifact semantic contract violations must be fixed" in prompt
    assert "must appear verbatim in the final file content" in prompt
    assert "agent_output/challenge_runtime/simulator.py" in prompt
    assert "deterministic simulator" in prompt
    assert "Add these exact required substrings: for layer in layers, self.run_task(task)" in prompt
    assert "Remove these forbidden substrings: plan_workflow(self.workflow)" in prompt


def test_corrective_prompt_builder_highlights_write_text_json_dumps_when_required(tmp_path: Path) -> None:
    builder = CorrectivePromptBuilder(tmp_path)
    prompt = builder.build_corrective_instruction(
        [
            {
                "reason": "artifact_semantic_contract_not_met",
                "violations": [
                    {
                        "path": "agent_output/tests/test_validator_and_planner.py",
                        "label": "validator and planner tests use real fixture paths",
                        "missing_tokens": ["write_text(json.dumps("],
                        "forbidden_tokens": [],
                    }
                ],
            }
        ],
        {
            "required_action_tools": ["write_file", "update_issue_status"],
            "required_statuses": ["code_review"],
            "required_write_paths": ["agent_output/tests/test_validator_and_planner.py"],
        },
    )

    assert "Add these exact required substrings: write_text(json.dumps(" in prompt
    assert "open(...)/json.dump(...)" in prompt


def test_corrective_prompt_builder_includes_preserve_tokens_when_present(tmp_path: Path) -> None:
    builder = CorrectivePromptBuilder(tmp_path)
    prompt = builder.build_corrective_instruction(
        [
            {
                "reason": "artifact_semantic_contract_not_met",
                "violations": [
                    {
                        "path": "agent_output/tests/test_validator_and_planner.py",
                        "label": "validator and planner tests use real fixture paths",
                        "missing_tokens": ["Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_valid.json'"],
                        "forbidden_tokens": ["tmp_path / 'workflow_valid.json'"],
                        "preserve_tokens": ["write_text(json.dumps(", "validate_workflow(str("],
                    }
                ],
            }
        ],
        {
            "required_action_tools": ["write_file", "update_issue_status"],
            "required_statuses": ["code_review"],
            "required_write_paths": ["agent_output/tests/test_validator_and_planner.py"],
        },
    )

    assert "Keep these exact substrings that are already correct in the current file:" in prompt
    assert "write_text(json.dumps(" in prompt
    assert "validate_workflow(str(" in prompt
