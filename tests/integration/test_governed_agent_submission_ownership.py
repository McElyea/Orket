"""Submission owns filesystem preparation and provider cleanup through interruption."""
import asyncio
import threading

import httpx
import pytest

from orket.application.services import governed_agent_submission_service as submission_service
from orket.application.services.governed_agent_submission_service import (
    GovernedAgentProviderOptions,
    GovernedAgentSubmission,
    submit_governed_agent,
)
from tests.helpers.governed_agent_cli import write_submission_files

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def submission_for(tmp_path):
    catalog, request, now = write_submission_files(tmp_path)
    return GovernedAgentSubmission(
        workload_id="governed-agent-loop", project_root=tmp_path, catalog_path=catalog,
        request_path=request, continuation_inputs_path=None, creation_timestamp_utc=now.isoformat(),
        decision_timestamps_utc=(now.isoformat(), now.isoformat()), next_lease_expiries_utc=(),
        provider=GovernedAgentProviderOptions(deterministic_fixture=True),
    )


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
# Layer: integration
async def test_submission_retains_real_preparation_worker_through_interruption(tmp_path, monkeypatch, mode):
    submission = submission_for(tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = submission_service._prepare_submission

    def held_preparation(value, **inputs):
        entered.set()
        assert release.wait(10)
        result = original(value, **inputs)
        finished.set()
        return result

    monkeypatch.setattr(submission_service, "_prepare_submission", held_preparation)

    async def invoke():
        if mode == "timeout":
            async with asyncio.timeout(0.1):
                await submit_governed_agent(db_path=tmp_path / "agent.sqlite3", submission=submission)
        else:
            await submit_governed_agent(db_path=tmp_path / "agent.sqlite3", submission=submission)

    task = asyncio.create_task(invoke())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if mode == "cancel":
            task.cancel()
        await asyncio.sleep(0.15)
        assert not task.done() and not finished.is_set()
        # Predeclared D responsiveness bound: unrelated work must finish within 0.5 seconds.
        await asyncio.wait_for(asyncio.sleep(0), timeout=0.5)
    finally:
        release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await task
    assert finished.is_set() and not (tmp_path / "agent.sqlite3").exists()


# Layer: integration
async def test_submission_closes_real_client_if_loop_composition_fails(tmp_path, monkeypatch):
    submission = submission_for(tmp_path)
    client = httpx.AsyncClient()
    original = submission_service._select_provider

    async def select(*arguments, **inputs):
        result = await original(*arguments, **inputs)
        result._live_provider = client
        return result

    def fail(**_):
        raise ValueError("composition-refused")

    monkeypatch.setattr(submission_service, "_select_provider", select)
    monkeypatch.setattr(submission_service, "build_governed_agent_loop_service", fail)
    # Match the selection's close protocol while retaining a real HTTP client's state.
    monkeypatch.setattr(client, "close", client.aclose, raising=False)
    try:
        with pytest.raises(ValueError, match="composition-refused"):
            await submit_governed_agent(db_path=tmp_path / "agent.sqlite3", submission=submission)
        assert client.is_closed
    finally:
        await client.aclose()
