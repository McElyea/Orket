"""Layer: integration. Actual native file ownership and controlled cancellation."""
from __future__ import annotations

import asyncio
import os
import sys
import threading
from pathlib import Path

import pytest

from orket.adapters.storage import epic_continuation_lock as locks
from orket.adapters.storage import local_file_lock as native
from orket.core.contracts.epic_approval_recovery import EpicContinuationLockRef
from tests.integration.test_epic_closeout_process import read_barrier

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[2]


# Layer: integration
async def test_cancellation_during_native_close_waits_for_release(tmp_path, monkeypatch):
    closing, release = threading.Event(), threading.Event()
    native_release = native._release

    def held_release(descriptor):
        closing.set()
        assert release.wait(15)
        native_release(descriptor)

    owner = locks.EpicContinuationLocks(tmp_path / "journal.sqlite3")
    monkeypatch.setattr(native, "_release", held_release)

    async def run():
        async with owner.hold("session"):
            pass

    task = asyncio.create_task(run())
    try:
        assert await asyncio.to_thread(closing.wait, 10)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        with pytest.raises(ValueError, match="owner_busy"):
            async with owner.hold("session"):
                pytest.fail("close had not completed")
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 15)
    async with owner.hold("session"):
        pass


@pytest.mark.parametrize("ending", ["release", "killed"])
# Layer: integration
async def test_native_holder_excludes_callers_and_releases_same_identity(tmp_path, ending):
    journal = tmp_path / "publication.sqlite3"
    child = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / "tests/helpers/epic_continuation_lock_worker.py"), str(journal), "session",
        env={**os.environ, "PYTHONPATH": str(ROOT), "ORKET_DISABLE_SANDBOX": "1"},
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    owner = locks.EpicContinuationLocks(journal)
    try:
        barrier = await asyncio.wait_for(read_barrier(child), 30)
        reference = EpicContinuationLockRef.model_validate(barrier["reference"])
        with pytest.raises(ValueError, match="owner_busy"):
            async with owner.hold("session", expected=reference):
                pytest.fail("A second native owner entered")
        async with owner.hold("other-session") as other:
            assert other.lock_path != reference.lock_path
        if ending == "killed":
            child.kill()
            await asyncio.wait_for(child.communicate(), 15)
        else:
            _, errors = await asyncio.wait_for(child.communicate(b"release\n"), 15)
            assert child.returncode == 0, errors.decode(errors="replace")
        async with owner.hold("session", expected=reference) as resumed:
            assert resumed == reference
        assert await asyncio.to_thread(Path(reference.lock_path).is_file)
    finally:
        if child.returncode is None:
            child.kill()
        await child.communicate()


# Layer: integration
async def test_cancelled_acquisition_waits_for_owned_thread_and_closes_descriptor(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    acquire = native._acquire

    def held_acquire(*args):
        observed = acquire(*args)
        entered.set()
        assert release.wait(10), "Owned acquisition thread was not released"
        return observed

    monkeypatch.setattr(native, "_acquire", held_acquire)
    owner = locks.EpicContinuationLocks(tmp_path / "journal.sqlite3")

    async def enter():
        async with owner.hold("session"):
            pytest.fail("Cancelled caller entered its continuation")

    task = asyncio.create_task(enter())
    try:
        assert await asyncio.to_thread(entered.wait, 10)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        with pytest.raises(ValueError, match="owner_busy"):
            async with owner.hold("session"):
                pytest.fail("Cancellation abandoned a live acquisition")
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 10)
    async with owner.hold("session"):
        pass  # The real descriptor was closed before cancellation returned.


# Layer: integration
async def test_exception_releases_local_owner_without_replacing_lock_file(tmp_path):
    owner = locks.EpicContinuationLocks(tmp_path / "journal.sqlite3")
    with pytest.raises(RuntimeError, match="fixture"):
        async with owner.hold("session") as reference:
            with pytest.raises(ValueError, match="owner_busy"):
                async with owner.hold("session"):
                    pytest.fail("Same-process caller entered concurrently")
            raise RuntimeError("fixture")
    async with owner.hold("session", expected=reference) as after:
        assert reference == after


# Layer: integration
async def test_replaced_lock_file_cannot_supply_retained_ownership(tmp_path):
    owner = locks.EpicContinuationLocks(tmp_path / "journal.sqlite3")
    async with owner.hold("session") as reference:
        path = Path(reference.lock_path)
    preserved = path.with_suffix(".preserved")
    await asyncio.to_thread(path.rename, preserved)
    with pytest.raises(ValueError, match="LOCK_CHANGED"):
        async with owner.hold("session", expected=reference):
            pytest.fail("Replacement inode supplied old ownership")
    assert await asyncio.to_thread(preserved.exists)


# Layer: integration
async def test_session_text_cannot_escape_selected_lock_directory(tmp_path):
    journal = tmp_path / "journal.sqlite3"
    session = "../../outside/identity:with:separators"
    async with locks.EpicContinuationLocks(journal).hold(session) as reference:
        assert reference.session_id == session
        assert Path(reference.lock_path).parent == journal.with_name(journal.name + ".continuations")
        assert len(Path(reference.lock_path).stem) == 64
