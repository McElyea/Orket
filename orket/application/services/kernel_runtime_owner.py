"""Explicit process-local Kernel state, selected input ports and native admission."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context, run_owned_thread
from orket.application.services.kernel_invocation_inputs import (
    bind_kernel_invocation_root,
    capture_kernel_invocation_root,
)
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.kernel_observation import KernelObservation


@dataclass(frozen=True, slots=True)
class KernelInputSources:
    utc_now: Callable[[], datetime] = field(repr=False)
    create_secret_token: Callable[[], str] = field(repr=False)
    create_credential_token_id: Callable[[], str] = field(repr=False)
    create_kernel_run_id: Callable[[], str] = field(repr=False)

    @classmethod
    def capture(cls, source: RuntimeInputService) -> KernelInputSources:
        return cls(source.utc_now, source.create_secret_token, source.create_credential_token_id, source.create_kernel_run_id)


class KernelStateLock:
    """Refuse native transitions after close has acquired the same state lock."""

    def __init__(self) -> None:
        self._native = RLock()
        self.closed = False

    def __enter__(self):
        self._native.acquire()
        if self.closed:
            self._native.release()
            raise RuntimeError("Kernel runtime is closed.")
        return self

    def __exit__(self, *args) -> None:
        self._native.release()

    def close(self) -> None:
        with self._native:
            self.closed = True


class KernelRuntime:
    """One caller-owned volatile state lifetime; no implicit default instance."""

    def __init__(self, *, runtime_inputs: RuntimeInputService | None = None, invocation_root: Path | None = None) -> None:
        selected = RuntimeInputService() if runtime_inputs is None else runtime_inputs
        self.sources = KernelInputSources.capture(selected)
        self.workspace_inputs = capture_kernel_invocation_root(invocation_root)
        self.lock = KernelStateLock()
        self.next_ledger_id = 1
        self.session_event_heads: dict[str, str] = {}
        self.session_canonical_state: dict[str, str] = {}
        self.ledger_by_session: dict[str, list[dict[str, Any]]] = {}
        self.events_by_digest: dict[str, dict[str, Any]] = {}
        self.admissions_by_proposal: dict[tuple[str, str], dict[str, Any]] = {}
        self.commit_results_by_key: dict[tuple, dict[str, Any]] = {}
        self.approvals_by_id: dict[str, dict[str, Any]] = {}
        self.pending_approvals_cache: dict[str, list[dict[str, Any]]] = {}
        self.tokens_by_hash: dict[str, dict[str, Any]] = {}

    @property
    def closed(self) -> bool:
        return self.lock.closed

    @contextmanager
    def activate(self) -> Iterator[KernelRuntime]:
        if self.closed:
            raise RuntimeError("Kernel runtime is closed.")
        token = _active_runtime.set(self)
        try:
            with bind_kernel_invocation_root(self.workspace_inputs):
                yield self
        finally:
            _active_runtime.reset(token)

    def close(self) -> None:
        require_sync_context(code="E_KERNEL_CLOSE_REQUIRES_ASYNC_OWNER")
        self.lock.close()

    @classmethod
    @asynccontextmanager
    async def open(cls, *, runtime_inputs: RuntimeInputService | None = None,
                   invocation_root: Path | None = None) -> AsyncIterator[KernelRuntime]:
        owner = cls(runtime_inputs=runtime_inputs, invocation_root=invocation_root)
        try:
            with owner.activate():
                yield owner
        finally:
            await run_owned_thread(owner.close, label="kernel-runtime-close")


# Carries an explicitly bound application owner into nested native workers.
# There is deliberately no lazy/default runtime and no global map proxy.
_active_runtime: ContextVar[KernelRuntime | None] = ContextVar("kernel_runtime_owner", default=None)


def current_kernel_runtime() -> KernelRuntime:
    owner = _active_runtime.get()
    if owner is None:
        raise RuntimeError("E_KERNEL_RUNTIME_OWNER_REQUIRED")
    if owner.closed:
        raise RuntimeError("Kernel runtime is closed.")
    return owner


def capture_kernel_observation() -> KernelObservation:
    return KernelObservation(current_kernel_runtime().sources.utc_now())
