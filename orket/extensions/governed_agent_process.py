from __future__ import annotations

import asyncio
import contextlib
import os
import signal

DIAGNOSTIC_TAIL_BYTES = 262_144


async def drain_diagnostic_tail(
    stream: asyncio.StreamReader | None,
    *,
    limit: int = DIAGNOSTIC_TAIL_BYTES,
) -> tuple[bytes, bool]:
    if stream is None:
        return b"", False
    tail = bytearray()
    truncated = False
    while chunk := await stream.read(8192):
        tail.extend(chunk)
        if len(tail) > limit:
            del tail[: len(tail) - limit]
            truncated = True
    return bytes(tail), truncated


async def await_process_stopped(
    process: asyncio.subprocess.Process,
    *,
    timeout_seconds: float,
) -> bool:
    try:
        await asyncio.wait_for(process.wait(), timeout=max(0.001, timeout_seconds))
        return True
    except TimeoutError:
        return False


async def terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec(
            "taskkill",
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
    else:
        kill_group = getattr(os, "killpg", None)
        if kill_group is not None:
            with contextlib.suppress(ProcessLookupError):
                await asyncio.to_thread(kill_group, process.pid, signal.SIGTERM)
    if process.returncode is None:
        process.kill()
    await process.wait()


def sanitized_agent_environment() -> dict[str, str]:
    allowed = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP")
    environment = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    environment.update({"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    return environment
