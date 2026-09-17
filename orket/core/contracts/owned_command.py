"""Observed lifetime and execution port for one application-admitted command."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class OwnedCommandResult:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    reason: str
    cleanup_confirmed: bool
    capture_complete: bool
    backend: str
    transport_pid: int
    supervisor_pid: int | None
    command_pid: int | None
    diagnostics: tuple[str, ...]

    def lifetime(self) -> dict[str, Any]:
        return {"schema_version": "owned_command.v1", "reason": self.reason,
                "cleanup_confirmed": self.cleanup_confirmed, "capture_complete": self.capture_complete,
                "backend": self.backend, "transport_pid": self.transport_pid, "supervisor_pid": self.supervisor_pid,
                "command_pid": self.command_pid, "diagnostics": list(self.diagnostics)}


class CommandExecutionUncertain(RuntimeError):
    """The caller must retain unresolved dispatch, without inventing a receipt."""

    def __init__(self, lifetime: OwnedCommandResult):
        super().__init__("E_COMMAND_EXECUTION_UNCERTAIN")
        self.lifetime = lifetime


class CommandRunner(Protocol):
    async def run(
        self, argv: Sequence[str], *, cwd: Path, timeout_seconds: float,
        environment: dict[str, str] | None = None, input_data: bytes | None = None,
        output_limit_bytes: int | None = None,
    ) -> OwnedCommandResult: ...
