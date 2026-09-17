"""Native acceptance child stopped between run insertion and event publication."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from tests.helpers.outward_authorization import FixedInputs, outward_api
from tests.integration.test_outward_run_admission import submission


async def main():
    original = OutwardRunEventStore.append

    async def pause_event(store, event, **kwargs):
        if event.event_type == "run_submitted":
            print("ADMISSION_BEFORE_EVENT", flush=True)
            await asyncio.Event().wait()
        return await original(store, event, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(OutwardRunEventStore, "append", pause_event)
        async with outward_api(Path(sys.argv[1]), FixedInputs()) as (client, _):
            await client.post("/v1/runs", json=submission("process-crash"))


if __name__ == "__main__":
    asyncio.run(main())
