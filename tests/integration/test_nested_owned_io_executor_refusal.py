"""Integration: closed native executor refusal retains its identity across an outer owner."""
from __future__ import annotations

import asyncio
import threading

import pytest

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from tests.integration.test_failure_diagnostic_refusals import _closed_executor

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_nested_owner_keeps_real_executor_refusal_without_worker_effects(record_property):
    executor, worker_thread = await asyncio.to_thread(_closed_executor)
    assert worker_thread != threading.get_ident()
    loop, previous = asyncio.get_running_loop(), asyncio.get_running_loop()._default_executor
    attempts, failures, graphs = [], [], []

    async def native_operation():
        try:
            await run_owned_thread(lambda: attempts.append("unexpected worker effect"), label="closed-executor-leaf")
        except RuntimeError as refusal:
            failures.append(refusal)
            graphs.append((refusal.__cause__, refusal.__context__))
            raise

    loop.set_default_executor(executor)
    try:
        with pytest.raises(RuntimeError, match="cannot schedule new futures after shutdown") as caught:
            await run_owned_io(native_operation, label="closed-executor-outer", preserve_failure=True)
        assert failures == [caught.value] and caught.value is failures[0]
        assert (caught.value.__cause__, caught.value.__context__) == graphs[0]
        assert not attempts
        record_property("closed_executor", {"real_worker_joined": True, "effects": [], "same_refusal": True})
    finally:
        loop._default_executor = previous
    assert await run_owned_thread(lambda: 17, label="restored-executor") == 17
