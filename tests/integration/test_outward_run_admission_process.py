"""Public API admission survives abrupt loss of its native process owner."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_authorization import outward_api
from tests.integration.test_outward_run_admission import submission

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]


async def barrier(child):
    while line := await child.stdout.readline():
        if line.strip() == b"ADMISSION_BEFORE_EVENT":
            return
    raise AssertionError("Child exited before the admission barrier")


# Layer: end-to-end
async def test_native_owner_death_does_not_leave_a_partial_admission(tmp_path, boundary):
    _, inputs, _ = boundary
    harness = await asyncio.to_thread(lambda: Path(__file__).resolve().parents[2])
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        str(harness / "tests/helpers/outward_admission_worker.py"),
        str(tmp_path),
        cwd=harness,
        env={**os.environ, "PYTHONPATH": str(harness), "ORKET_DISABLE_SANDBOX": "1"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(barrier(child), 15)
        child.kill()
        await asyncio.wait_for(child.communicate(), 15)
        assert child.returncode is not None and child.returncode != 0
    finally:
        if child.returncode is None:
            child.kill()
            await asyncio.wait_for(child.communicate(), 15)
    async with outward_api(tmp_path, inputs) as (client, context):
        assert await context.outward_run_store.get("process-crash") is None
        assert await context.outward_run_event_store.list_for_run("process-crash") == []
        response = await client.post("/v1/runs", json=submission("process-crash"))
        assert response.status_code == 200, response.text
        assert [event.event_type for event in await context.outward_run_event_store.list_for_run("process-crash")] == [
            "run_submitted"
        ]
