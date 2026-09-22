"""Sample the bound owner's selected run identity after capturing its workspace."""

from orket.adapters.execution.owned_io import require_sync_context
from orket.application.services.kernel_invocation_inputs import capture_kernel_invocation_root
from orket.application.services.kernel_runtime_owner import current_kernel_runtime
from orket.core.contracts.kernel_run_inputs import KernelRunInputs


def capture_kernel_run_inputs(workspace_root: str) -> KernelRunInputs:
    require_sync_context(code="E_KERNEL_INVOCATION_REQUIRES_ASYNC_OWNER")
    owner = current_kernel_runtime()
    workspace = capture_kernel_invocation_root(workspace_root)
    return KernelRunInputs(owner.sources.create_kernel_run_id(), workspace)
