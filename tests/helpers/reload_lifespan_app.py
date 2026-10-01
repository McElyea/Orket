"""Controlled real ASGI lifecycle for spawned-reloader integration tests."""
from __future__ import annotations

import _signal
import asyncio
import ctypes
import gc
import os
import sys
import time
from contextlib import asynccontextmanager
from multiprocessing.util import Finalize
from pathlib import Path

from fastapi import FastAPI

from orket.interfaces.api_reload_runtime import run_reloading_api_server

ROOT = Path(__file__).resolve().parent
PID = os.getpid()


class InterpreterFinalizer:
    """Hold real interpreter teardown after CPython clears Python signal handlers."""

    def __init__(self):
        self.held = str(ROOT / f"{PID}-interpreter-finalization-held")
        self.done = str(ROOT / f"{PID}-interpreter-finalization-done")
        self.release = str(ROOT / "release-finalizer")
        self.failure = os.environ["RELOAD_TEST_FINALIZER"] == "fail"
        # Module globals may be cleared before __del__; retain native callables.
        self.open, self.write, self.close = os.open, os.write, os.close
        self.access, self.exit = os.access, os._exit
        self.sleep, self.delay, self.clock = time.sleep, 0.02, time.monotonic
        if os.name == "nt":
            # Python's sleep uses the SIGINT event already closed by signal fini.
            self.sleep = ctypes.WinDLL("kernel32").Sleep
            self.sleep.argtypes, self.sleep.restype = [ctypes.c_ulong], None
            self.delay = 20
        self.finalizing, self.handler = sys.is_finalizing, _signal.getsignal
        self.flags, self.sigint = os.O_CREAT | os.O_WRONLY, _signal.SIGINT
        self.cycle = self

    def __del__(self):
        if not self.finalizing() or self.handler(self.sigint) is not None:
            self.exit(19)
        descriptor = self.open(self.held, self.flags, 0o600)
        self.write(descriptor, b"interpreter-finalizing; python-signal-handler-cleared")
        self.close(descriptor)
        deadline = self.clock() + 10
        while not self.access(self.release, 0):
            if self.clock() >= deadline:
                self.exit(18)
            self.sleep(self.delay)
        self.close(self.open(self.done, self.flags, 0o600))
        if self.failure:
            self.exit(17)


def arm_interpreter_finalizer():
    # Explicit interpreter GC still runs after signal teardown. Disable earlier
    # automatic GC so it cannot collect the unreachable cycle before that point.
    gc.disable()
    InterpreterFinalizer()


async def mark(event):
    await asyncio.to_thread((ROOT / f"{PID}-{event}").touch)


async def wait_for_release(phase):
    if os.environ.get("RELOAD_TEST_HOLD") != phase:
        return
    await mark(phase + "-held")
    # The release comes from an independent parent process through its filesystem.
    while not await asyncio.to_thread((ROOT / "release").exists):  # noqa: ASYNC110
        await asyncio.sleep(0.02)


def finish_process():
    """Native process-finalization callback, after the server event loop closes."""
    (ROOT / f"{PID}-process-finalization-held").touch()
    deadline = time.monotonic() + 10
    while not (ROOT / "release-finalizer").exists():
        if time.monotonic() >= deadline:
            os._exit(18)
        time.sleep(0.02)
    (ROOT / f"{PID}-process-finalization-done").touch()
    if os.environ["RELOAD_TEST_FINALIZER"] == "fail":
        os._exit(17)


@asynccontextmanager
async def lifespan(app):
    if os.environ.get("RELOAD_TEST_FINALIZER"):
        if os.environ.get("RELOAD_TEST_FINALIZER_STAGE") == "interpreter":
            Finalize(None, arm_interpreter_finalizer, exitpriority=0)
        else:
            Finalize(None, finish_process, exitpriority=0)
    await wait_for_release("startup")
    if os.environ.get("RELOAD_TEST_FAILURE") == "startup":
        raise RuntimeError("controlled startup failure")
    await mark("started")
    yield
    await wait_for_release("shutdown")
    if os.environ.get("RELOAD_TEST_FAILURE") == "shutdown":
        await mark("cleanup-failed")
        raise RuntimeError("controlled cleanup failure")
    await mark("closed")


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"pid": PID}


@app.get("/held")
async def held():
    await wait_for_release("request")
    await mark("request-completed")
    return {"pid": PID}


if __name__ == "__main__":
    run_reloading_api_server("server:app", host="127.0.0.1", port=int(os.environ["RELOAD_TEST_PORT"]),
                             reload_excludes=[])
