"""Inputs for actual legacy Kernel policy reads and local triplet effects."""


def policy_payload(permissions=None):
    return {
        "contract_version": "kernel_api/v1",
        "policy_id": "kernel_capability_policy_v1",
        "policy_source": "policy://test/selected",
        "policy_version": "test-v1",
        "default_permissions": [],
        "role_task_permissions": {"coder": {"edit": ["file.write"] if permissions is None else permissions}},
    }


def turn_request(root):
    return {
        "contract_version": "kernel_api/v1",
        "turn_id": "turn-policy",
        "run_handle": {"run_id": "run-policy", "workspace_root": str(root)},
        "turn_input": {
            "context": {"role": "coder", "task": "edit"},
            "tool_call": {"action": "file.write", "resource": "fixture"},
            "stage_triplet": {"stem": "fixture", "body": {"value": "captured"}, "links": {}, "manifest": {}},
        },
    }
