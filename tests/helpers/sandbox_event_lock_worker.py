"""Own actual replay until an explicit release or process termination."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import orket
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services import sandbox_lifecycle_event_service
from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService


async def main():
    spool, database = map(Path, sys.argv[1:])
    repository = AsyncSandboxLifecycleRepository(database)

    class HeldRepository:
        async def append_event(self, record):
            print(json.dumps({"barrier": "replay_owner_held", "origin": orket.__file__,
                              "service_origin": sandbox_lifecycle_event_service.__file__,
                              "executable": sys.executable, "prefix": sys.prefix}), flush=True)
            if (await asyncio.to_thread(sys.stdin.readline)).strip() != "release":
                raise ValueError("Expected explicit fixture release")
            await repository.append_event(record)

    await SandboxLifecycleEventService(repository=HeldRepository(), spool_path=spool).replay_spool()


if __name__ == "__main__":
    asyncio.run(main())
