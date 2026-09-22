from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from orket.runtime.config.contract_assets import DEFAULT_KERNEL_CAPABILITY_POLICY_PATH

pytestmark = pytest.mark.contract

CONTRACTS_ROOT = Path("docs/projects/archive/OS-Stale-2026-02-28/contracts")


def test_kernel_capability_policy_artifact_shape_is_valid() -> None:
    policy_path = DEFAULT_KERNEL_CAPABILITY_POLICY_PATH
    payload = json.loads(policy_path.read_text(encoding="utf-8"))

    assert payload["contract_version"] == "kernel_api/v1"
    assert payload["policy_id"] == "kernel_capability_policy_v1"
    assert payload["policy_source"] == "policy://orket/kernel/v1/default"
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
    policy_path = DEFAULT_KERNEL_CAPABILITY_POLICY_PATH
    schema_path = CONTRACTS_ROOT / "kernel-capability-policy-v1.schema.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
