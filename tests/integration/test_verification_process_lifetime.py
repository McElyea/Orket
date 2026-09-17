"""Integration proof through public verification, with independent process observers."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from orket.application.services.runtime_verifier import RuntimeVerifier

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).with_name("verification_lifetime_worker.py")


def observe_processes(root):
    processes = []
    for path in sorted(root.glob("ready-*.json")):
        try:
            processes.append(psutil.Process(json.loads(path.read_text(encoding="utf-8"))["pid"]))
        except psutil.NoSuchProcess:
            # Already exited is valid for cleanup, but cannot satisfy await_tree's
            # requirement to independently observe all three live identities.
            continue
    return processes


def running(process):
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def stop_observed(processes):
    # Test cleanup uses only fixture PIDs, whose psutil identities include creation time.
    for process in processes:
        if running(process):
            process.kill()
    psutil.wait_procs(processes, timeout=5)


async def await_tree(root):
    read_failure = None
    for _ in range(200):
        try:
            processes = await asyncio.to_thread(observe_processes, root)
        except PermissionError as exc:
            # Windows can deny a just-renamed marker briefly. Keep the same
            # bounded startup wait and require all three actual process identities.
            read_failure = exc
            await asyncio.sleep(0.025)
            continue
        if len(processes) == 3:
            return processes
        await asyncio.sleep(0.025)
    raise AssertionError("Fixture process tree did not become ready") from read_failure


async def await_fixture_bootstrap(root, process, output):
    # Fixture interpreter/import/store setup is separate from the existing
    # five-second command-tree admission bound and post-cancellation exit bounds.
    async with asyncio.timeout(30):
        while not await asyncio.to_thread((root / "fixture-bootstrap-ready").exists):
            if process.returncode is not None:
                stdout, stderr = await output
                raise AssertionError(f"Fixture exited before bootstrap: {stdout!r} {stderr!r}")
            await asyncio.sleep(0.025)


async def assert_stopped(processes, root):
    assert not await asyncio.to_thread(lambda: any(running(p) for p in processes))
    before = await asyncio.to_thread(lambda: [p.read_bytes() for p in sorted(root.glob("heartbeat-*.txt"))])
    await asyncio.sleep(0.15)
    after = await asyncio.to_thread(lambda: [p.read_bytes() for p in sorted(root.glob("heartbeat-*.txt"))])
    assert before == after


@pytest.mark.parametrize("stop", ["cancel", "repeated-cancel", "timeout", "leader-exit", "leader-failure"])
@pytest.mark.parametrize("flags", [[], ["detached", "ignore-term"]], ids=["ordinary", "detached-resistant"])
# Layer: integration
async def test_public_runtime_verification_stops_children_and_grandchildren(tmp_path, stop, flags, caplog):
    org = SimpleNamespace(process_rules={
        "runtime_verifier_commands": [
            [sys.executable, str(WORKER), str(tmp_path), "2", *flags, stop],
            [sys.executable, "-c", "from pathlib import Path; Path('next-command').touch()"],
        ],
        # Three real interpreters must be observed before exercising timeout.
        # This is a lifetime fixture, not a one-second startup performance gate.
        "runtime_verifier_timeout_sec": 5 if stop == "timeout" else 10,
    })
    task = asyncio.create_task(RuntimeVerifier(tmp_path, organization=org).verify())
    processes = []
    try:
        processes = await await_tree(tmp_path)
        if stop in {"cancel", "repeated-cancel"}:
            task.cancel()
            if stop == "repeated-cancel":
                for _ in range(20):
                    if task.done():
                        break
                    await asyncio.sleep(0.01)
                    task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
            events = [r.orket_record["data"] for r in caplog.records if r.message == "verification_process_cancelled"]
            assert len(events) == 1
            lifetime = events[0]
        else:
            if stop in {"leader-exit", "leader-failure"}:
                await asyncio.to_thread((tmp_path / "release-leader").touch)
            # Timeout includes its configured five-second run budget plus five
            # seconds for cleanup; success also starts the second interpreter.
            result = await asyncio.wait_for(asyncio.shield(task), 10 if stop in {"leader-exit", "timeout"} else 5)
            if stop == "timeout":
                assert not result.ok and result.failure_breakdown == {"timeout": 1}
            elif stop == "leader-failure":
                assert not result.ok and result.failure_breakdown == {"command_failed": 1}
                assert result.command_results[0]["returncode"] == 7
            else:
                assert result.ok and result.command_results[0]["returncode"] == 0
            lifetime = result.command_results[0]["process_lifetime"]
        assert lifetime["cleanup_confirmed"] is True
        assert lifetime["backend"] == ("windows_job" if sys.platform == "win32" else "linux_subreaper")
        assert not await asyncio.to_thread(psutil.pid_exists, lifetime["supervisor_pid"])
        assert not await asyncio.to_thread(psutil.pid_exists, lifetime["transport_pid"])
        await assert_stopped(processes, tmp_path)
        assert await asyncio.to_thread((tmp_path / "next-command").exists) is (stop == "leader-exit")
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
