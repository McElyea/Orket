import pytest
import json
import os
from unittest.mock import MagicMock
from pathlib import Path
from orket.services.gitea_webhook_handler import GiteaWebhookHandler
from orket.services.webhook_db import WebhookDatabase

@pytest.fixture
async def handler(monkeypatch, tmp_path):
    # REAL DATABASE on temporary disk
    db_path = tmp_path / "webhooks.db"
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    
    # We monkeypatch WebhookDatabase to use our temp path
    with patch("orket.services.webhook_db.Path") as mock_path:
        # This is a bit of a hack since WebhookDatabase hardcodes its path
        # In a real refactor, we should make the path injectable.
        pass

    h = GiteaWebhookHandler(workspace=tmp_path)
    
    # Simulating the network without mocking the whole class
    # We only mock the specific transport or the low-level call
    h.client = MagicMock()
    h.client.post = AsyncMock(return_value=MagicMock(status_code=200))
    h.client.patch = AsyncMock(return_value=MagicMock(status_code=200))
    
    yield h
    await h.close()

from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_pr_cycle_tracking_real_db(monkeypatch, tmp_path):
    """
    Test PR cycle tracking using a real SQLite database.
    No mocking of the database logic.
    """
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "test_webhooks.db"
    
    # We need a way to tell WebhookDatabase where to go
    # For this test, we'll patch the constructor to use a temp db
    with patch("orket.services.webhook_db.sqlite3") as mock_sql:
        import sqlite3
        real_conn = sqlite3.connect(db_path)
        mock_sql.connect.return_value = real_conn
        
        handler = GiteaWebhookHandler(workspace=tmp_path)
        handler.client = AsyncMock()
        handler.client.post.return_value = MagicMock(status_code=200)

        payload = {
            "pull_request": {"number": 42},
            "review": {"user": {"login": "bot"}, "state": "changes_requested"},
            "repository": {"name": "repo", "owner": {"login": "org"}}
        }

        # Cycle 1
        await handler.handle_webhook("pull_request_review", payload)
        # Cycle 2
        await handler.handle_webhook("pull_request_review", payload)
        # Cycle 3 - Should Trigger Escalation
        res = await handler.handle_webhook("pull_request_review", payload)
        
        assert res["status"] == "escalated"
        
        # Verify the REAL database state
        cursor = real_conn.cursor()
        cursor.execute("SELECT cycle_count FROM pr_cycles WHERE pr_number = 42")
        row = cursor.fetchone()
        assert row[0] == 3
        
        real_conn.close()

@pytest.mark.asyncio
async def test_auto_reject_after_4_cycles(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "reject_test.db"
    
    with patch("orket.services.webhook_db.sqlite3") as mock_sql:
        import sqlite3
        real_conn = sqlite3.connect(db_path)
        mock_sql.connect.return_value = real_conn
        
        handler = GiteaWebhookHandler(workspace=tmp_path)
        handler.client = AsyncMock()
        handler.client.post.return_value = MagicMock(status_code=200)
        handler.client.patch.return_value = MagicMock(status_code=200)

        payload = {
            "pull_request": {"number": 99},
            "review": {"user": {"login": "bot"}, "state": "changes_requested"},
            "repository": {"name": "repo", "owner": {"login": "org"}}
        }

        # Run through 4 cycles
        for _ in range(4):
            await handler.handle_webhook("pull_request_review", payload)
            
        # Verify database shows rejected
        cursor = real_conn.cursor()
        cursor.execute("SELECT status FROM pr_cycles WHERE pr_number = 99")
        assert cursor.fetchone()[0] == "rejected"
        
        # Verify PR was closed via API
        assert handler.client.patch.called
        real_conn.close()