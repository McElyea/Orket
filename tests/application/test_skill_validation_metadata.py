from __future__ import annotations

from orket.application.services.skills_validator import validate_skill_manifest


def _valid_manifest() -> dict:
    return {
        "skill_contract_version": "1.0.5",
        "skill_id": "skill.demo",
        "skill_version": "1.2.3",
        "description": "Demo skill",
        "manifest_digest": "sha256:abc123",
        "entrypoints": [
            {
                "entrypoint_id": "main",
                "runtime": "python",
                "runtime_version": "3.11.0",
                "command": "python run.py",
                "working_directory": ".",
                "input_schema": {},
                "output_schema": {},
                "error_schema": {},
                "args_fingerprint_fields": ["input.task"],
                "result_fingerprint_fields": ["result.summary"],
                "side_effect_fingerprint_fields": [],
                "requested_permissions": {},
                "required_permissions": {},
                "tool_profile_id": "tool.demo",
                "tool_profile_version": "1.0.0",
            }
        ],
    }


def test_skill_validation_metadata_marks_valid_manifest_as_deterministic_eligible() -> None:
    payload = _valid_manifest()
    result = validate_skill_manifest(payload)

    assert result["contract_valid"] is True
    assert result["determinism_eligible"] is True
    assert result["fingerprint_completeness"] == "complete"
    assert result["trust_level"] == "validated"
    assert result["errors"] == []


def test_skill_validation_metadata_is_deterministic_for_identical_payload() -> None:
    payload = _valid_manifest()
    first = validate_skill_manifest(payload)
    second = validate_skill_manifest(payload)
    assert first == second


def test_skill_validation_metadata_flags_side_effect_declaration_gaps() -> None:
    payload = _valid_manifest()
    payload["entrypoints"][0]["side_effect_categories"] = ["network.http"]
    payload["entrypoints"][0]["side_effect_fingerprint_fields"] = []

    result = validate_skill_manifest(payload)
    assert result["determinism_eligible"] is False
    assert result["side_effect_risk"] == "undeclared"
    assert any(item.endswith(":side_effect_undeclared") for item in result["errors"])
