from __future__ import annotations

import pytest

from orket.application.services.skill_adapter import (
    build_tool_profile_bindings,
    synthesize_role_tool_profile_bindings,
)


def _manifest() -> dict:
    return {
        "skill_contract_version": "1.0.5",
        "skill_id": "skill.demo",
        "skill_version": "1.0.0",
        "description": "Demo skill",
        "manifest_digest": "sha256:abc123",
        "entrypoints": [
            {
                "entrypoint_id": "write-main",
                "runtime": "python",
                "runtime_version": "3.11.0",
                "command": "python run.py",
                "working_directory": ".",
                "runtime_limits": {"max_execution_time": 10, "max_memory": 256},
                "input_schema": {},
                "output_schema": {},
                "error_schema": {},
                "args_fingerprint_fields": ["input.path"],
                "result_fingerprint_fields": ["result.ok"],
                "side_effect_fingerprint_fields": [],
                "requested_permissions": {"filesystem": ["write"]},
                "required_permissions": {"filesystem": ["write"]},
                "tool_profile_id": "write_file",
                "tool_profile_version": "1.1.0",
            }
        ],
    }


def test_build_tool_profile_bindings_from_manifest() -> None:
    bindings = build_tool_profile_bindings(_manifest())
    assert "write_file" in bindings
    row = bindings["write_file"]
    assert row["entrypoint_id"] == "write-main"
    assert row["tool_profile_version"] == "1.1.0"
    assert row["runtime_limits"]["max_execution_time"] == 10
    assert row["required_permissions"] == {"filesystem": ["write"]}


def test_build_tool_profile_bindings_rejects_duplicate_tool_profile_ids() -> None:
    payload = _manifest()
    payload["entrypoints"].append(
        {
            **payload["entrypoints"][0],
            "entrypoint_id": "write-main-2",
        }
    )
    with pytest.raises(ValueError, match="duplicate tool_profile_id binding"):
        build_tool_profile_bindings(payload)


def test_synthesize_role_tool_profile_bindings_creates_deterministic_defaults() -> None:
    bindings = synthesize_role_tool_profile_bindings(["write_file", "read_file", "write_file"])
    assert sorted(bindings.keys()) == ["read_file", "write_file"]
    assert bindings["write_file"]["tool_profile_version"] == "role-tools.v1"
