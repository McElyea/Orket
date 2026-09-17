"""Shared application ownership of native command lifetime through cancellation."""
from __future__ import annotations

import asyncio
from pathlib import Path

from orket.adapters.execution.owned_command_process import execute_owned_command
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
                  output_limit_bytes=None) -> OwnedCommandResult:
        stop = asyncio.Event()
        owner = asyncio.create_task(execute_owned_command(
            argv=argv, cwd=cwd, timeout_seconds=timeout_seconds, environment=environment, input_data=input_data,
            stop=stop, output_limit_bytes=output_limit_bytes))
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
