from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

CONTRACTS_ROOT = Path("docs/projects/archive/OS-Stale-2026-02-28/contracts")


def test_kernel_capability_policy_artifact_shape_is_valid() -> None:
    policy_path = Path("model/core/contracts/kernel_capability_policy_v1.json")
    payload = json.loads(policy_path.read_text(encoding="utf-8"))

    assert payload["contract_version"] == "kernel_api/v1"
    assert payload["policy_id"] == "kernel_capability_policy_v1"
    assert payload["policy_source"] == str(policy_path).replace("\\", "/")
    assert isinstance(payload["policy_version"], str) and payload["policy_version"]

    default_permissions = payload["default_permissions"]
    assert isinstance(default_permissions, list)
    assert all(isinstance(item, str) and item for item in default_permissions)

    role_task_permissions = payload["role_task_permissions"]
    assert isinstance(role_task_permissions, dict)
    assert role_task_permissions
    for role, tasks in role_task_permissions.items():
        assert isinstance(role, str) and role
        assert isinstance(tasks, dict) and tasks
        for task, permissions in tasks.items():
            assert isinstance(task, str) and task
            assert isinstance(permissions, list)
            assert all(isinstance(item, str) and item for item in permissions)


def test_kernel_capability_policy_artifact_conforms_to_schema() -> None:
    policy_path = Path("model/core/contracts/kernel_capability_policy_v1.json")
    schema_path = CONTRACTS_ROOT / "kernel-capability-policy-v1.schema.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
