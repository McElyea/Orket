"""Cleanup failures and cancellation cannot preserve a successful caller result."""
import asyncio

import pytest

from orket.application.services.runtime_result_lifetime import execute_collection_member
from orket.interfaces.cli import _finish_named_run
from tests.helpers.runtime_result import published_result

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


# Layer: contract
async def test_cli_emits_no_success_before_required_cleanup(capsys):
    class Owner:
        async def close(self):
            raise OSError("cleanup unavailable")

    with pytest.raises(OSError, match="cleanup unavailable"):
        await _finish_named_run(Owner(), published_result())
    assert capsys.readouterr().out == ""


# Layer: contract
async def test_collection_cleanup_failure_keeps_member_truth_but_blocks_success():
    expected = published_result()

    class Owner:
        async def run_card(self, *args, **kwargs):
            return expected

        async def close(self):
            raise OSError("cleanup unavailable")

    result = await execute_collection_member(create=Owner, creation={}, target="one", session_id="fixture-session",
                                              build_id="build", execution={})
    assert not result.succeeded and result.observation == "unresolved"
    assert result.run == expected.run and result.final_truth == expected.final_truth
    assert "cleanup unavailable" in result.reason


# Layer: contract
async def test_repeated_cancellation_joins_cli_cleanup_before_propagating(capsys):
    entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class Owner:
        async def close(self):
            entered.set()
            await release.wait()
            finished.set()

    task = asyncio.create_task(_finish_named_run(Owner(), published_result()))
    await asyncio.wait_for(entered.wait(), 5)
    try:
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and not finished.is_set()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
    assert finished.is_set() and capsys.readouterr().out == ""
