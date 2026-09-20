"""Integration: actual Git checkout filters remain owned through install interruption."""
from __future__ import annotations

import asyncio
import shlex
import sys
from pathlib import Path

import pytest

from orket.application.services.command_process_supervisor import CommandProcessCancelled
from tests.helpers.sdk_lifetime import owned_fixture_processes
from tests.integration.test_extension_installation_ownership import _commit, _installed
from tests.integration.test_verification_process_lifetime import WORKER, assert_stopped, await_tree, stop_observed

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
FILTER = Path(__file__).parents[1] / "helpers/extension_git_filter.py"


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_real_git_filter_tree_is_stopped_before_install_interruption_returns(tmp_path, monkeypatch, stop):
    source, manager, previous = await _installed(tmp_path)
    before = await asyncio.to_thread(manager.catalog_path.read_bytes)
    await asyncio.to_thread((source / ".gitattributes").write_text, "payload.bin filter=owned\n", encoding="utf-8")
    await asyncio.to_thread((source / "payload.bin").write_bytes, b"admitted payload")
    await asyncio.to_thread(_commit, source)
    command = " ".join(shlex.quote(Path(value).as_posix()) for value in (sys.executable, FILTER, tmp_path, WORKER))
    for key, value in {"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "filter.owned.smudge",
                       "GIT_CONFIG_VALUE_0": command, "GIT_CONFIG_KEY_1": "filter.owned.required",
                       "GIT_CONFIG_VALUE_1": "true"}.items():
        monkeypatch.setenv(key, value)
    operation = asyncio.create_task(manager.install_from_repo(str(source)))
    request, processes = operation, []
    try:
        await await_tree(tmp_path)
        processes = await asyncio.to_thread(owned_fixture_processes, tmp_path)
        assert len(processes) >= 5  # Git/filter plus the independently observed three-child fixture.
        started = asyncio.get_running_loop().time()
        await asyncio.to_thread((tmp_path / "responsive").write_text, "ready", encoding="utf-8")
        assert asyncio.get_running_loop().time() - started < 0.5
        if stop == "timeout":
            request = asyncio.create_task(asyncio.wait_for(operation, 0.05))
            with pytest.raises(TimeoutError) as failure:
                await asyncio.wait_for(request, 6)
            cancellation = failure.value.__cause__
        else:
            operation.cancel()
            await asyncio.sleep(0.01)
            operation.cancel()
            with pytest.raises(asyncio.CancelledError) as failure:
                await asyncio.wait_for(operation, 6)
            cancellation = failure.value
        assert type(cancellation) is asyncio.CancelledError
        assert isinstance(cancellation.__cause__, CommandProcessCancelled)
        lifetime = cancellation.__cause__.lifetime
        assert lifetime.cleanup_confirmed and lifetime.capture_complete
        await assert_stopped(processes, tmp_path)
        assert await asyncio.to_thread(manager.catalog_path.read_bytes) == before
        await asyncio.to_thread(manager._verify_extension_integrity, previous)
    finally:
        await asyncio.to_thread((tmp_path / "release-filter").touch)
        if not operation.done():
            operation.cancel()
        await asyncio.wait_for(asyncio.gather(request, operation, return_exceptions=True), 8)
        await asyncio.to_thread(stop_observed, processes)
