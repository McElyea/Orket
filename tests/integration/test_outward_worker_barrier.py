"""Native fixture shutdown cannot authorize another provider invocation."""
from __future__ import annotations

import asyncio

import pytest

from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_effect_worker import finish_effect_worker, paused_effect_worker
from tests.helpers.outward_model_admission import count_calls, queue_run

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("signal", [b"", b"stop\n", b"continue\n"])
# Layer: integration
async def test_native_model_barrier_requires_explicit_continuation(tmp_path, boundary, signal):
    _, inputs, calls = boundary
    await queue_run(tmp_path, inputs, calls[:1])
    async with paused_effect_worker(tmp_path, "bt0-run", "model_claim") as process:
        if signal == b"continue\n":
            response = await finish_effect_worker(process)
            assert response[0] == 200 and response[1]["status"] == "approval_required"
            assert await count_calls(tmp_path) == 1
        else:
            stdout, stderr = await asyncio.wait_for(process.communicate(signal), 20)
            assert await count_calls(tmp_path) == 0, (stdout.decode(), stderr.decode())
            assert process.returncode != 0
    assert process.returncode is not None
    assert not (tmp_path / "first.txt").exists()
