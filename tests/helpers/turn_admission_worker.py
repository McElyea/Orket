"""Pause an actual admission immediately before or after its transaction commit."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.core.domain import AttemptState
from tests.integration.test_turn_recovery_transaction import INPUTS


async def main():
    db, boundary = Path(sys.argv[1]), sys.argv[2]
    files = AsyncFileTools(db.parent)

    async def pause():
        await files.write_file('admission-ready.txt', boundary)
        await asyncio.Event().wait()

    original = AsyncControlPlaneExecutionRepository.save_attempt_record

    async def save_attempt(repository, *, record):
        result = await original(repository, record=record)
        if boundary == 'before-commit' and record.attempt_state is AttemptState.EXECUTING:
            await pause()
        return result

    AsyncControlPlaneExecutionRepository.save_attempt_record = save_attempt
    service = build_turn_tool_control_plane_service(db)
    await service.begin_execution(**INPUTS, resume_mode=False)
    await pause()


if __name__ == '__main__':
    asyncio.run(main())
