"""Real engine/card storage with controlled review execution; no provider claim."""

import asyncio
from types import SimpleNamespace

import pytest

import orket.orchestration.engine as engine_module
from orket.application.services.gitea_webhook_runtime import build_webhook_runtime
from orket.application.services.webhook_configuration import capture_webhook_configuration
from tests.helpers.webhook import environment

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def prepare(tmp_path, monkeypatch):
    config = capture_webhook_configuration(tmp_path, environment=environment(tmp_path))
    handler = await build_webhook_runtime(config)
    engine = await asyncio.to_thread(
        engine_module.OrchestrationEngine, tmp_path, config_root=tmp_path, db_path=handler._review_db_path
    )
    await engine.cards.save({"id": "ISSUE-HELD", "summary": "Held review", "seat": "developer"})
    monkeypatch.setattr(engine_module, "OrchestrationEngine", lambda *args, **kwargs: engine)
    return handler, engine


async def admit(handler):
    return await handler.handle_webhook(
        "pull_request",
        {
            "action": "opened",
            "pull_request": {"number": 20, "title": "ISSUE-HELD review"},
            "repository": {"name": "fixture", "owner": {"login": "fixture"}},
        },
    )


async def test_shutdown_waits_for_active_review_cleanup_and_real_engine_close(tmp_path, monkeypatch):
    handler, engine = await prepare(tmp_path, monkeypatch)
    entered, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    closed = []
    original_close = engine.close

    async def held_review(issue_id):
        assert issue_id == "ISSUE-HELD"
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleanup.set()
            await release.wait()

    async def close_engine():
        await original_close()
        closed.append(True)

    monkeypatch.setattr(engine, "run_card", held_review)
    monkeypatch.setattr(engine, "close", close_engine)
    closing = None
    try:
        assert (await admit(handler))["status"] == "success"
        await asyncio.wait_for(entered.wait(), 3)
        assert (await engine.cards.get_by_id("ISSUE-HELD")).status.value == "code_review"
        closing = asyncio.create_task(handler.close())
        await asyncio.wait_for(cleanup.wait(), 3)
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        assert not closing.done() and not closed and not handler.client.is_closed
        assert not handler.accepting_work
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await closing
        await handler.close()
        assert closed == [True] and handler.closed and handler.client.is_closed
        assert handler.active_background_task_count == handler.active_request_count == 0
    finally:
        release.set()
        if closing:
            await asyncio.gather(closing, return_exceptions=True)
        await handler.close()


@pytest.mark.parametrize("failure_at", ["review", "engine-close"])
async def test_completed_review_failure_prevents_clean_shutdown_claim(tmp_path, monkeypatch, failure_at):
    handler, engine = await prepare(tmp_path, monkeypatch)
    original_close = engine.close
    finished = asyncio.Event()
    failure = RuntimeError("controlled " + failure_at + " failure")

    async def review(_):
        if failure_at == "review":
            raise failure
        return SimpleNamespace(succeeded=True)

    async def close_engine():
        try:
            await original_close()
            if failure_at == "engine-close":
                raise failure
        finally:
            finished.set()

    monkeypatch.setattr(engine, "run_card", review)
    monkeypatch.setattr(engine, "close", close_engine)
    await admit(handler)
    await asyncio.wait_for(finished.wait(), 3)
    for _ in range(20):
        if not handler.accepting_work:
            break
        await asyncio.sleep(0)
    assert not handler.accepting_work
    for _ in range(2):
        with pytest.raises(RuntimeError, match="teardown failed") as observed:
            await handler.close()
        assert observed.value.__cause__ is failure
    assert not handler.closed and handler.client.is_closed
    # The repository's autouse engine fixture closes direct engines once more.
    # Remove this test's fault only after both retained failure assertions.
    monkeypatch.setattr(engine, "close", original_close)
