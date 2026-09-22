"""Explicit value inputs for deterministic Kernel run handles and workspace selection."""

from dataclasses import dataclass
from pathlib import PurePath
from typing import Any

CONTRACT_VERSION = "kernel_api/v1"
DEFAULT_VISIBILITY_MODE = "local_only"
DEFAULT_WORKSPACE_ROOT = ".orket_kernel"


@dataclass(frozen=True, slots=True)
class KernelWorkspaceInputs:
    root: str

    def __post_init__(self) -> None:
        if type(self.root) is not str or not self.root or not PurePath(self.root).is_absolute():
            raise ValueError("E_KERNEL_WORKSPACE_ABSOLUTE_STRING_REQUIRED")


@dataclass(frozen=True, slots=True)
class KernelRunInputs:
    run_id: str
    workspace: KernelWorkspaceInputs

    def __post_init__(self) -> None:
        if type(self.run_id) is not str or not self.run_id:
            raise ValueError("E_KERNEL_RUN_ID_NONEMPTY_STRING_REQUIRED")
        if not isinstance(self.workspace, KernelWorkspaceInputs):
            raise TypeError("E_KERNEL_WORKSPACE_INPUTS_REQUIRED")


def build_start_run_response(inputs: KernelRunInputs, visibility_mode: Any) -> dict[str, Any]:
    if not isinstance(inputs, KernelRunInputs):
        raise TypeError("E_KERNEL_RUN_INPUTS_REQUIRED")
    return {
        "contract_version": CONTRACT_VERSION,
        "run_handle": {
            "contract_version": CONTRACT_VERSION,
            "run_id": inputs.run_id,
            "visibility_mode": visibility_mode,
            "workspace_root": inputs.workspace.root,
        },
    }
