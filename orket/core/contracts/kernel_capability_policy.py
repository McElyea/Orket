"""Immutable, explicitly supplied inputs for the legacy Kernel capability surface."""

from dataclasses import dataclass
from typing import Any

from orket_extension_sdk import FrozenJson


def _permissions(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _validate(payload: Any) -> None:
    fields = {
        "contract_version",
        "policy_id",
        "policy_source",
        "policy_version",
        "default_permissions",
        "role_task_permissions",
    }
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError("E_KERNEL_POLICY_INVALID: expected exact policy fields")
    if payload["contract_version"] != "kernel_api/v1" or payload["policy_id"] != "kernel_capability_policy_v1":
        raise ValueError("E_KERNEL_POLICY_INVALID: unsupported contract or policy ID")
    if any(not isinstance(payload[key], str) or not payload[key] for key in ("policy_source", "policy_version")):
        raise ValueError("E_KERNEL_POLICY_INVALID: nonempty provenance required")
    if not _permissions(payload["default_permissions"]):
        raise ValueError("E_KERNEL_POLICY_INVALID: invalid default permissions")
    roles = payload["role_task_permissions"]
    if not isinstance(roles, dict) or not roles:
        raise ValueError("E_KERNEL_POLICY_INVALID: nonempty role mapping required")
    for role, tasks in roles.items():
        if not isinstance(role, str) or not role or not isinstance(tasks, dict) or not tasks:
            raise ValueError("E_KERNEL_POLICY_INVALID: invalid role mapping")
        if any(not isinstance(task, str) or not task or not _permissions(items) for task, items in tasks.items()):
            raise ValueError("E_KERNEL_POLICY_INVALID: invalid task permissions")


@dataclass(frozen=True, slots=True)
class KernelCapabilityPolicy:
    """Policy bytes are detached once; each result is a new caller-owned value."""

    document: FrozenJson

    def __post_init__(self) -> None:
        if not isinstance(self.document, FrozenJson):
            raise TypeError("Kernel capability policy requires FrozenJson")
        _validate(self.document.thaw())

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "KernelCapabilityPolicy":
        return cls(FrozenJson.freeze(payload))

    def evidence(self, context: dict[str, Any]) -> dict[str, str]:
        policy = self.document.thaw()
        # Context overrides remain declared caller metadata, not authenticated provenance.
        source = context.get("policy_source") or policy["policy_source"]
        version = context.get("policy_version") or policy["policy_version"]
        return {
            "policy_ref": str(context.get("policy_ref", source)),
            "capability_source": str(source),
            "capability_version": str(version),
        }

    def permissions(self, role: str, task: str, context: dict[str, Any]) -> list[str]:
        items = context.get("permissions")
        if not isinstance(items, list):
            policy = self.document.thaw()
            items = policy["role_task_permissions"].get(role, {}).get(task, policy["default_permissions"])
        return sorted({str(item) for item in items if str(item)})
