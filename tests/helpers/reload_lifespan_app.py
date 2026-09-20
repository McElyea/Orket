"""Controlled real ASGI lifecycle for spawned-reloader integration tests."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from orket.interfaces.api_reload_runtime import run_reloading_api_server

ROOT = Path(__file__).resolve().parent
PID = os.getpid()


async def mark(event):
    await asyncio.to_thread((ROOT / f"{PID}-{event}").touch)


async def wait_for_release(phase):
    if os.environ.get("RELOAD_TEST_HOLD") != phase:
        return
    await mark(phase + "-held")
    # The release comes from an independent parent process through its filesystem.
    while not await asyncio.to_thread((ROOT / "release").exists):  # noqa: ASYNC110
        await asyncio.sleep(0.02)


@asynccontextmanager
async def lifespan(app):
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
