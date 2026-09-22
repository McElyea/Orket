"""Controlled scheduling around actual Kernel and SQLite application paths."""

import asyncio
import threading
import time
from types import SimpleNamespace

import aiosqlite

from orket.interfaces.api import create_api_app
from tests.helpers.outward_authorization import TEST_API_KEY


def kernel_app(root):
    return create_api_app(
        project_root=root,
        environment={
            "ORKET_API_KEY": TEST_API_KEY,
            "ORKET_DISABLE_SANDBOX": "1",
            "ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED": "0",
            "ORKET_TTS_BACKEND": "null",
            "ORKET_STATE_BACKEND_MODE": "local",
            "ORKET_RUN_LEDGER_MODE": "sqlite",
            "ORKET_DURABLE_ROOT": str(root / "state"),
            "ORKET_GITEA_ARTIFACT_EXPORT": "0",
        },
    )


def hold_native(monkeypatch, owner, name):
    hold = SimpleNamespace(entered=threading.Event(), release=threading.Event(), expired=False, worker=None)
    original = getattr(owner, name)

    def held(*args, **kwargs):
        if not hold.entered.is_set():
            hold.worker = threading.get_ident()
            hold.entered.set()
            # A fixed .8s watchdog makes an old event-loop-blocking implementation fail without hanging.
            hold.expired = not hold.release.wait(0.8)
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, held)
    return hold


async def responsive_sqlite(database, record_property):
    started = time.perf_counter()
    async with aiosqlite.connect(database) as connection:
        await connection.execute("CREATE TABLE IF NOT EXISTS response_probe (value INTEGER)")
        await connection.execute("INSERT INTO response_probe VALUES (42)")
        await connection.commit()
        assert await (await connection.execute("SELECT value FROM response_probe")).fetchone() == (42,)
    elapsed = time.perf_counter() - started
    record_property("responsive_sqlite_seconds", elapsed)
    assert elapsed < 0.5


async def interrupt_owned(task, release, *, timed):
    if timed:
        waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
        await asyncio.sleep(0.04)
    else:
        waiter = task
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.02)
    if task.done() or waiter.done():
        release.set()
        await asyncio.gather(task, waiter, return_exceptions=True)
        raise AssertionError("admitted publication escaped its caller")
    release.set()
    return waiter
