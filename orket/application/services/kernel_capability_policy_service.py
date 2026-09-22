"""Capture one policy observation before the native Kernel evaluates a request."""

from pathlib import Path

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.storage.kernel_capability_policy_reader import read_kernel_capability_policy
from orket.core.contracts.kernel_capability_policy import KernelCapabilityPolicy
from orket.runtime.config.contract_assets import DEFAULT_KERNEL_CAPABILITY_POLICY_PATH


def capture_kernel_capability_policy(*, policy_path: Path | None = None) -> KernelCapabilityPolicy:
    require_sync_context(code="E_KERNEL_POLICY_REQUIRES_ASYNC_OWNER")
    selected = DEFAULT_KERNEL_CAPABILITY_POLICY_PATH if policy_path is None else policy_path
    path = selected.absolute()
    return KernelCapabilityPolicy.from_payload(read_kernel_capability_policy(path))


def selected_kernel_capability_policy(policy: KernelCapabilityPolicy | None) -> KernelCapabilityPolicy:
    if policy is None:
        return capture_kernel_capability_policy()
    if not isinstance(policy, KernelCapabilityPolicy):
        raise TypeError("Kernel capability policy requires typed inputs")
    return policy
