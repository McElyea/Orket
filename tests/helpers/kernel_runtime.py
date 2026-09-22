"""Explicit native Kernel ownership for direct-call tests."""

from dataclasses import replace

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.kernel_runtime_owner import KernelRuntime, current_kernel_runtime


@pytest.fixture
def kernel_runtime():
    owner = KernelRuntime()
    try:
        with owner.activate():
            yield owner
    finally:
        owner.close()


def select_test_clock(monkeypatch, clock):
    """Select a controlled input port; transition/state/event implementations stay real."""
    owner = current_kernel_runtime()
    monkeypatch.setattr(owner, "sources", replace(owner.sources, utc_now=clock))


async def engine_events(engine, session_id):
    from orket.kernel.v1.nervous_system_runtime_state import list_events_for_session

    def observe():
        with engine.kernel_gateway.runtime.activate():
            return list_events_for_session(session_id)

    return await run_owned_thread(observe, label="observe-engine-kernel-ledger")


class ObservedKernelLock:
    """Observe admission to the actual owner's native lock without replacing locking."""

    def __init__(self, original, attempted):
        self.original, self.attempted = original, attempted

    @property
    def closed(self):
        return self.original.closed

    def close(self):
        self.original.close()

    def __enter__(self):
        self.attempted.set()
        return self.original.__enter__()

    def __exit__(self, *args):
        return self.original.__exit__(*args)
