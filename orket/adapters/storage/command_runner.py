from __future__ import annotations

import asyncio
import io
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.storage.async_executor_service import run_coroutine_blocking
from orket.core.contracts.owned_command import CommandRunner as OwnedCommandRunner
from orket.core.contracts.owned_command import OwnedCommandResult

side_effecting = True


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    lifetime: OwnedCommandResult | None = field(default=None, compare=False, repr=False)


class SandboxCommandUncertain(subprocess.SubprocessError):
    """No completed command receipt; retain possible daemon-side effects."""

    def __init__(self, lifetime: OwnedCommandResult):
        super().__init__("E_SANDBOX_COMMAND_EXECUTION_UNCERTAIN")
        self.lifetime = lifetime


class SandboxCommandTimeout(subprocess.TimeoutExpired):
    def __init__(self, timeout: float, lifetime: OwnedCommandResult):
        # Arguments, environment and captured output may contain credentials.
        super().__init__("<sandbox command>", timeout)
        self.lifetime = lifetime


class CommandRunner:
    """Execute through the application-selected owner and captured process inputs."""

    def __init__(self, *, owner: OwnedCommandRunner, cwd: Path,
                 environment: Mapping[str, str], timeout_seconds: float):
        if not cwd.is_absolute():
            raise ValueError("E_SANDBOX_COMMAND_CWD_MUST_BE_ABSOLUTE")
        self._owner = owner
        self._cwd = Path(cwd)
        self._environment = dict(environment)
        self._timeout_seconds = timeout_seconds

    async def run_async(self, *cmd: str) -> CommandResult:
        result = await self._run(cmd, self._timeout_seconds)
        return CommandResult(result.returncode, result.stdout.decode(), result.stderr.decode(), result)

    def run_sync(self, *cmd: str, timeout: float | None = None) -> CommandResult:
        require_sync_context(code="E_SANDBOX_COMMAND_REQUIRES_WORKER")
        result = run_coroutine_blocking(self._run(cmd, self._timeout_seconds if timeout is None else timeout))
        with io.TextIOWrapper(io.BytesIO(result.stdout)) as stdout, io.TextIOWrapper(io.BytesIO(result.stderr)) as stderr:
            return CommandResult(result.returncode, stdout.read(), stderr.read(), result)

    async def _run(self, cmd: tuple[str, ...], budget_seconds: float) -> OwnedCommandResult:
        owner, cwd, environment = self._owner, self._cwd, dict(self._environment)
        try:
            result = await owner.run(tuple(cmd), cwd=cwd, environment=environment, timeout_seconds=budget_seconds)
        except asyncio.CancelledError as exc:
            # asyncio.timeout on Python 3.11 recognizes the exact base type.
            # The owner's cleanup observation remains attached as the cause.
            raise asyncio.CancelledError("Sandbox command cancelled") from exc
        if result.cleanup_confirmed and result.capture_complete:
            if result.reason == "completed" and type(result.returncode) is int:
                return result
            if result.reason == "timeout":
                raise SandboxCommandTimeout(budget_seconds, result)
        raise SandboxCommandUncertain(result)
