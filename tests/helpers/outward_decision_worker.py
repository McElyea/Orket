"""Independent authenticated BT-1 decision worker, synchronized through stdout."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import aiosqlite

from orket.settings import set_runtime_settings_context
from tests.helpers.outward_authorization import FixedInputs, outward_api


async def run(root: Path, proposal_id: str, decision: str, api_key: str) -> None:
    os.environ["ORKET_API_KEY"] = api_key
    original = aiosqlite.Connection.execute
    signaled = False

    def observe(connection, sql, *args, **kwargs):
        nonlocal signaled
        if not signaled and " ".join(sql.upper().split()) == "BEGIN IMMEDIATE":
            signaled = True
            print("BT1_WRITER_WAITING", flush=True)
        return original(connection, sql, *args, **kwargs)

    inputs = FixedInputs()
    if decision == "expire":
        inputs.now += timedelta(seconds=10)
    async with outward_api(root, inputs, api_key=api_key) as (client, context):
        # Initialize every store before the parent takes the competing writer lock.
        async with context.outward_approval_service.unit_of_work.transaction():
            pass
        print("BT1_SCHEMA_READY", flush=True)
        command = await asyncio.wait_for(asyncio.to_thread(sys.stdin.readline), timeout=20)
        assert command.strip() == "decide", "Decision worker was not released by its parent"
        aiosqlite.Connection.execute = observe
        try:
            if decision == "expire":
                response = await client.get(f"/v1/approvals/{proposal_id}")
                payload = {"approval": response.json()}
            else:
                response = await client.post(
                    f"/v1/approvals/{proposal_id}/{decision}",
                    json={"reason": "independent operator denial"} if decision == "deny" else {},
                )
                payload = response.json()
            result = [response.status_code, payload]
        finally:
            aiosqlite.Connection.execute = original
    print("BT1_RESPONSE=" + json.dumps(result), flush=True)


if __name__ == "__main__":
    # Decision contention uses explicit test settings; preference migration has
    # separate native-lock proof and must not race the decision setup handshake.
    set_runtime_settings_context(user_settings={}, user_preferences={})
    asyncio.run(run(Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]))
