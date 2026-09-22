"""Capture and bind one immutable application environment through Kernel workers."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from orket.core.contracts.kernel_run_inputs import KernelWorkspaceInputs
from orket.project_paths import default_project_root


@dataclass(frozen=True, slots=True)
class KernelEnvironmentSnapshot:
    values: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        copied = dict(self.values)
        if any(type(key) is not str or type(value) is not str for key, value in copied.items()):
            raise TypeError("E_KERNEL_ENVIRONMENT_STRING_REQUIRED")
        object.__setattr__(self, "values", MappingProxyType(copied))


# Carries explicit immutable application input into a worker; never a global cache.
_environment: ContextVar[KernelEnvironmentSnapshot | None] = ContextVar("kernel_invocation_environment", default=None)


def capture_kernel_environment(environment: Mapping[str, str] | None = None) -> KernelEnvironmentSnapshot:
    selected = _environment.get() if environment is None else None
    return (
        selected
        if selected is not None
        else KernelEnvironmentSnapshot(os.environ if environment is None else environment)
    )


@contextmanager
def bind_kernel_environment(snapshot: KernelEnvironmentSnapshot) -> Iterator[None]:
    if not isinstance(snapshot, KernelEnvironmentSnapshot):
        raise TypeError("E_KERNEL_ENVIRONMENT_SNAPSHOT_REQUIRED")
    token = _environment.set(snapshot)
    try:
        yield
    finally:
        _environment.reset(token)


# Carries an admitted lexical root into nested native workers; no cached default.
_invocation_root: ContextVar[KernelWorkspaceInputs | None] = ContextVar("kernel_invocation_root", default=None)


def capture_kernel_invocation_root(root: str | Path | None = None) -> KernelWorkspaceInputs:
    selected = _invocation_root.get()
    if root is None:
        return selected if selected is not None else KernelWorkspaceInputs(str(default_project_root()))
    path = Path(root)
    if path.drive and not path.is_absolute():
        raise ValueError("E_KERNEL_DRIVE_RELATIVE_WORKSPACE_UNSUPPORTED")
    if not path.is_absolute():
        base = Path(selected.root) if selected is not None else default_project_root()
        path = base / path
    return KernelWorkspaceInputs(str(path))


@contextmanager
def bind_kernel_invocation_root(snapshot: KernelWorkspaceInputs) -> Iterator[None]:
    if not isinstance(snapshot, KernelWorkspaceInputs):
        raise TypeError("E_KERNEL_WORKSPACE_INPUTS_REQUIRED")
    token = _invocation_root.set(snapshot)
    try:
        yield
    finally:
        _invocation_root.reset(token)
