from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    """Infrastructure adapter for subprocess execution."""

    async def run_async(self, *cmd: str) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return CommandResult(
            returncode=process.returncode or 0,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )

    def run_sync(self, *cmd: str, timeout: Optional[int] = None) -> CommandResult:
        result = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout)
        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
