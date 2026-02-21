from __future__ import annotations

import pytest

from orket.application.services.skill_loader import SkillLoaderError, load_skill_manifest_or_raise


def test_skill_loader_rejects_schema_invalid_manifest_with_canonical_error() -> None:
    payload = {
        "skill_contract_version": "1.0.5",
        "skill_id": "skill.invalid",
        "skill_version": "1.0.0",
        # missing required description/manifest_digest/entrypoints
    }
    with pytest.raises(SkillLoaderError) as exc:
        load_skill_manifest_or_raise(payload)

    err = exc.value
    assert err.error_code == "ERR_SCHEMA_INVALID"
    assert err.validation_stage == "schema"
    assert err.retryable is False
    serialized = err.to_payload()
    assert serialized["skill_id"] == "skill.invalid"
    assert serialized["skill_version"] == "1.0.0"


def test_skill_loader_rejects_unsupported_contract_version() -> None:
    payload = {
        "skill_contract_version": "9.9.9",
        "skill_id": "skill.unsupported",
        "skill_version": "1.0.0",
        "description": "Unsupported contract version",
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
    with pytest.raises(SkillLoaderError) as exc:
        load_skill_manifest_or_raise(payload)

    err = exc.value
    assert err.error_code == "ERR_CONTRACT_UNSUPPORTED_VERSION"
    assert err.validation_stage == "contract_version"
    assert err.skill_contract_version_seen == "9.9.9"


def test_skill_loader_rejects_runtime_unpinned_with_entrypoint_context() -> None:
    payload = {
        "skill_contract_version": "1.0.5",
        "skill_id": "skill.runtime.unpinned",
        "skill_version": "1.0.0",
        "description": "Runtime pinning missing",
        "manifest_digest": "sha256:abc123",
        "entrypoints": [
            {
                "entrypoint_id": "main",
                "runtime": "python",
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
    with pytest.raises(SkillLoaderError) as exc:
        load_skill_manifest_or_raise(payload)

    err = exc.value
    assert err.error_code == "ERR_RUNTIME_UNPINNED"
    assert err.validation_stage == "runtime"
    assert err.entrypoint_id == "main"


def test_skill_loader_rejects_permission_undeclared() -> None:
    payload = {
        "skill_contract_version": "1.0.5",
        "skill_id": "skill.permission.invalid",
        "skill_version": "1.0.0",
        "description": "Permission mismatch",
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
                "requested_permissions": {"filesystem": ["read"]},
                "required_permissions": {"filesystem": ["write"]},
                "tool_profile_id": "tool.demo",
                "tool_profile_version": "1.0.0",
            }
        ],
    }
    with pytest.raises(SkillLoaderError) as exc:
        load_skill_manifest_or_raise(payload)

    err = exc.value
    assert err.error_code == "ERR_PERMISSION_UNDECLARED"
    assert err.validation_stage == "permissions"
