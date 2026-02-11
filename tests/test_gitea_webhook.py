import pytest
import aiosqlite
from unittest.mock import AsyncMock, MagicMock

from orket.services.gitea_webhook_handler import GiteaWebhookHandler
from orket.services.webhook_db import WebhookDatabase


@pytest.mark.asyncio
async def test_pr_cycle_tracking_real_db(monkeypatch, tmp_path):
    """
    Test PR cycle tracking using the real async webhook database.
    """
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "test_webhooks.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = AsyncMock()
    handler.client.post.return_value = MagicMock(status_code=200)

    payload = {
        "pull_request": {"number": 42},
        "review": {"user": {"login": "bot"}, "state": "changes_requested"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    await handler.handle_webhook("pull_request_review", payload)
    await handler.handle_webhook("pull_request_review", payload)
    res = await handler.handle_webhook("pull_request_review", payload)

    assert res["status"] == "escalated"
    cycle_count = await handler.db.get_pr_cycle_count("org/repo", 42)
    assert cycle_count == 3

    await handler.close()


@pytest.mark.asyncio
async def test_auto_reject_after_4_cycles(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "reject_test.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = AsyncMock()
    handler.client.post.return_value = MagicMock(status_code=200)
    handler.client.patch.return_value = MagicMock(status_code=200)

    payload = {
        "pull_request": {"number": 99},
        "review": {"user": {"login": "bot"}, "state": "changes_requested"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    for _ in range(4):
        await handler.handle_webhook("pull_request_review", payload)

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT status FROM pr_review_cycles WHERE pr_key = ?",
            ("org/repo#99",),
        )
        row = await cursor.fetchone()

    assert row["status"] == "rejected"
    assert handler.client.patch.called

    await handler.close()
