from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


async def run_process(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float | None = None,
) -> ProcessResult:
    merged_env = _build_env(env)
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        env=merged_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        if timeout_seconds and timeout_seconds > 0:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_seconds)
        else:
            stdout, stderr = await process.communicate()
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return ProcessResult(
            returncode=124,
            stdout="",
            stderr=f"Command timed out after {timeout_seconds} seconds",
            timed_out=True,
        )
    return ProcessResult(
        returncode=process.returncode or 0,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        timed_out=False,
    )


def _build_env(env: Mapping[str, str] | None) -> dict[str, str]:
    merged = dict(os.environ)
    merged.setdefault("TZ", "UTC")
    merged.setdefault("LC_ALL", "C")
    merged.setdefault("PYTHONHASHSEED", "0")
    if env:
        merged.update({str(k): str(v) for k, v in env.items()})
    return merged
