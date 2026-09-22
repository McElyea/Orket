"""Shared application ownership of native command lifetime through cancellation."""
from __future__ import annotations

import asyncio
import math
from pathlib import Path

from orket.adapters.execution.owned_command_limits import jsonl_request_frames
from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.application.services.process_input_service import capture_process_context
from orket.core.contracts.owned_command import OwnedCommandResult
from orket.logging import log_event


class CommandProcessCancelled(asyncio.CancelledError):
    """Cancellation with the actual cleanup observation, including uncertainty."""

    def __init__(self, lifetime: OwnedCommandResult):
        super().__init__("Owned command cancelled")
        self.lifetime = lifetime


async def _record_cancellation(result, workspace, event_type):
    publication = asyncio.create_task(asyncio.to_thread(
        log_event, event_type, result.lifetime(), workspace))
    while True:
        try:
            await asyncio.shield(publication)
            return
        except asyncio.CancelledError:
            if publication.cancelled():
                raise


class CommandProcessSupervisor:
    def __init__(self, workspace: Path, *, cancellation_event: str):
        self.workspace = workspace
        self.cancellation_event = cancellation_event

    async def run(self, argv, *, cwd, timeout_seconds, environment=None, input_data=None,
                  output_limit_bytes=None, jsonl_requests=None, io_timeout_seconds=None) -> OwnedCommandResult:
        cwd, environment = capture_process_context(cwd=cwd, environment=environment)
        argv, input_data = tuple(argv), None if input_data is None else bytes(input_data)
        stop = asyncio.Event()
        protocol = ({} if jsonl_requests is None else
                    dict(jsonl_requests=jsonl_request_frames(jsonl_requests), io_timeout_seconds=io_timeout_seconds))
        owner = asyncio.create_task(execute_owned_command(
            argv=argv, cwd=cwd, timeout_seconds=timeout_seconds, environment=environment, input_data=input_data,
            stop=stop, output_limit_bytes=output_limit_bytes, **protocol))
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(owner)
                break
            except asyncio.CancelledError:
                if owner.cancelled():
                    raise
                cancelled = True
                stop.set()
        if cancelled:
            try:
                await _record_cancellation(result, self.workspace, self.cancellation_event)
            except (OSError, ValueError, RuntimeError) as exc:
                raise CommandProcessCancelled(result) from exc
            raise CommandProcessCancelled(result)
        return result

    async def run_jsonl(self, argv, *, requests, cwd, io_timeout_seconds, environment) -> OwnedCommandResult:
        frames, timeout = jsonl_request_frames(requests), float(io_timeout_seconds)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("E_COMMAND_JSONL_TIMEOUT_INVALID")
        return await self.run(argv, cwd=cwd, environment=environment,
                              timeout_seconds=(2 * len(frames) + 2) * timeout,
                              jsonl_requests=frames, io_timeout_seconds=timeout)
