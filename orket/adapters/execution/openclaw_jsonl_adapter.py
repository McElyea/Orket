from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_command_limits import decode_jsonl_response
from orket.core.contracts.owned_command import CommandExecutionUncertain, JsonlCommandRunner

side_effecting = True


class OpenClawSubprocessError(RuntimeError):
    """Subprocess failure carrying the number of completed adapter responses."""

    def __init__(self, message: str, *, completed_count: int) -> None:
        super().__init__(message)
        self.completed_count = int(completed_count)


@dataclass(frozen=True)
class PartialAdapterResult:
    responses: list[dict[str, Any]]
    failed_at: int | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.failed_at is None and self.error is None

    @property
    def completed_count(self) -> int:
        return len(self.responses)


class OpenClawJsonlSubprocessAdapter:
    """Minimal JSONL subprocess bridge for OpenClaw-style tool-intent traffic."""

    def __init__(
        self,
        *,
        command: Sequence[str],
        runner: JsonlCommandRunner,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        io_timeout_seconds: float = 30.0,
    ) -> None:
        if not command:
            raise ValueError("command is required")
        if not math.isfinite(float(io_timeout_seconds)):
            raise ValueError("io_timeout_seconds must be finite")
        self.runner = runner
        self.command = tuple(str(part) for part in command)
        self.cwd = str(cwd) if cwd is not None else None
        self.env = dict(env) if env is not None else None
        self.io_timeout_seconds = max(1.0, float(io_timeout_seconds))

    async def run_requests(self, requests: list[dict[str, Any]]) -> PartialAdapterResult:
        command, root = tuple(self.command), Path.cwd()
        directory = root if self.cwd is None else root / self.cwd
        environment = dict(os.environ if self.env is None else self.env)
        frames = tuple(json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
                       for request in requests)
        result = await self.runner.run_jsonl(command, requests=frames, cwd=directory,
            environment=environment, io_timeout_seconds=self.io_timeout_seconds)
        if (not result.cleanup_confirmed or result.reason == "cancelled"
                or (not result.capture_complete and result.reason != "launch_failed")):
            raise CommandExecutionUncertain(result)
        responses = []
        for line in result.stdout.split(b"\n")[:len(frames)]:
            try:
                response = decode_jsonl_response(line)
            except ValueError:
                break
            responses.append(response)
        if result.reason == "completed" and result.returncode == 0 and len(responses) == len(frames):
            return PartialAdapterResult(responses=responses)
        detail = "; ".join((result.reason, *result.diagnostics))
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        return self._partial_failure(responses, f"subprocess failed: {detail}; exit={result.returncode}; {stderr}")

    @staticmethod
    def _partial_failure(responses: list[dict[str, Any]], message: str) -> PartialAdapterResult:
        return PartialAdapterResult(
            responses=list(responses),
            failed_at=len(responses),
            error=str(OpenClawSubprocessError(message, completed_count=len(responses))),
        )


__all__ = ["OpenClawJsonlSubprocessAdapter", "OpenClawSubprocessError", "PartialAdapterResult"]
