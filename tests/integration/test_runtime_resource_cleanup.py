"""Integration proof of native close failures and follower resources in real runtimes."""
import asyncio
import sqlite3

import pytest

from tests.helpers.runtime_cleanup_ports import (
    AsyncCleanupPort,
    NativeCleanupPort,
    create_cleanup_runtime,
    exception_leaves,
    release_cleanup_runtime,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("kind", ["engine", "pipeline", "context"])
@pytest.mark.parametrize("port_type", [NativeCleanupPort, AsyncCleanupPort], ids=["sync", "async"])
@pytest.mark.parametrize("failing", [1, 2])
async def test_runtime_close_attempts_followers_after_native_failure(tmp_path, monkeypatch, kind, port_type, failing):
    monkeypatch.chdir(tmp_path)
    ports = [await asyncio.to_thread(port_type, tmp_path / f"resource-{index}.sqlite3", failure=index < failing)
             for index in range(4)]
    runtime = None
    try:
        runtime, owner = await create_cleanup_runtime(tmp_path, kind, ports)
        with pytest.raises((sqlite3.OperationalError, ExceptionGroup)) as caught:
            await owner.close()
        assert all(port.attempts >= 1 for port in ports)
        assert not getattr(owner, "_closed", False)
        leaves = exception_leaves(caught.value)
        assert all(isinstance(error, sqlite3.OperationalError) for error in leaves)
        assert all(any(error in leaves for error in port.errors) for port in ports[:failing])
        for index, port in enumerate(ports):
            assert await asyncio.to_thread(port.observe_closed) is (index >= failing)
        for port in ports:
            port.failure = False
        await owner.close()
        assert all(await asyncio.gather(*(asyncio.to_thread(port.observe_closed) for port in ports)))
    finally:
        await release_cleanup_runtime(runtime, ports)


@pytest.mark.parametrize("kind, attribute", [("engine", "_pipeline"), ("pipeline", "sandbox_orchestrator")])
@pytest.mark.parametrize("port_type", [NativeCleanupPort, AsyncCleanupPort], ids=["sync", "async"])
async def test_outer_runtime_close_reaches_context_after_earlier_failure(
    tmp_path, monkeypatch, kind, attribute, port_type,
):
    monkeypatch.chdir(tmp_path)
    ports = [await asyncio.to_thread(port_type, tmp_path / f"resource-{index}.sqlite3", failure=index == 0)
             for index in range(4)]
    runtime = None
    try:
        runtime, owner = await create_cleanup_runtime(tmp_path, kind, ports)
        # Observe each outer cleanup boundary using a real failing native port.
        # Restore the original owner before final cleanup; no runtime action is fabricated.
        with monkeypatch.context() as boundary:
            boundary.setattr(owner, attribute, ports[0])
            with pytest.raises((sqlite3.OperationalError, ExceptionGroup)):
                await owner.close()
            assert not owner._closed
            assert all(await asyncio.gather(*(asyncio.to_thread(port.observe_closed) for port in ports[1:])))
    finally:
        await release_cleanup_runtime(runtime, ports)
