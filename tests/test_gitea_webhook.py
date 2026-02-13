import pytest
import aiosqlite

from orket.services.gitea_webhook_handler import GiteaWebhookHandler
from orket.services.webhook_db import WebhookDatabase


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


class _FakeClient:
    def __init__(self):
        self.post_calls = []
        self.patch_calls = []

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return _FakeResponse(status_code=200)

    async def patch(self, url, **kwargs):
        self.patch_calls.append((url, kwargs))
        return _FakeResponse(status_code=200)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_pr_cycle_tracking_real_db(monkeypatch, tmp_path):
    """
    Test PR cycle tracking using the real async webhook database.
    """
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "test_webhooks.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = _FakeClient()

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
    handler.client = _FakeClient()

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
    assert len(handler.client.patch_calls) >= 1

    await handler.close()
