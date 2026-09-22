"""Layer: contract. Pure typed policy validation, detachment and deterministic decisions."""

import pytest

from orket.core.contracts.kernel_capability_policy import KernelCapabilityPolicy
from orket.kernel.v1.api import authorize_tool_call, resolve_capability
from tests.helpers.kernel_capability_probe import policy_payload

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "field,value",
    [
        ("contract_version", "wrong"),
        ("policy_id", "wrong"),
        ("policy_source", ""),
        ("policy_version", 1),
        ("default_permissions", [1]),
        ("default_permissions", [""]),
        ("role_task_permissions", {}),
        ("role_task_permissions", {"": {"edit": []}}),
        ("role_task_permissions", {"coder": {}}),
        ("role_task_permissions", {"coder": {"": []}}),
        ("role_task_permissions", {"coder": {"edit": [False]}}),
        ("extra_field", True),
    ],
)
def test_malformed_policy_is_not_an_empty_policy(field, value):
    payload = policy_payload()
    payload[field] = value
    with pytest.raises(ValueError, match="E_KERNEL_POLICY_INVALID"):
        KernelCapabilityPolicy.from_payload(payload)


@pytest.mark.asyncio
async def test_explicit_policy_is_detached_repeatable_and_does_not_read_files(monkeypatch):
    import orket.application.services.kernel_capability_policy_service as service

    def forbidden_read(path):
        raise AssertionError(f"explicit policy unexpectedly read {path}")

    payload = policy_payload()
    policy = KernelCapabilityPolicy.from_payload(payload)
    payload["role_task_permissions"]["coder"]["edit"].clear()
    monkeypatch.setattr(service, "read_kernel_capability_policy", forbidden_read)
    request = {"contract_version": "kernel_api/v1", "role": "coder", "task": "edit"}
    first = resolve_capability(request, policy_inputs=policy)
    first["capability_plan"]["permissions"].append("foreign.execute")
    second = resolve_capability(request, policy_inputs=policy)
    assert second["capability_plan"]["permissions"] == ["file.write"]
    assert second == resolve_capability(request, policy_inputs=KernelCapabilityPolicy.from_payload(policy_payload()))
    auth = {"contract_version": "kernel_api/v1", "context": request, "tool_request": {"action": "file.write"}}
    assert authorize_tool_call(auth, policy_inputs=policy)["decision"]["result"] == "GRANT"
    with pytest.raises(TypeError, match="typed inputs"):
        resolve_capability(request, policy_inputs=payload)


def test_explicit_empty_permissions_remain_a_valid_deny_policy():
    policy = KernelCapabilityPolicy.from_payload(policy_payload([]))
    assert policy.permissions("coder", "edit", {}) == []
    assert policy.permissions("unknown", "unknown", {}) == []
    assert policy.permissions("coder", "edit", {"permissions": ["a", "a"]}) == ["a"]
    assert policy.evidence({"policy_source": "declared", "policy_version": "caller"}) == {
        "policy_ref": "declared",
        "capability_source": "declared",
        "capability_version": "caller",
    }
