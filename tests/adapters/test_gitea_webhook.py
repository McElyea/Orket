import asyncio

import aiosqlite
import pytest

from orket.adapters.vcs.gitea_webhook_handler import GiteaWebhookHandler
from orket.adapters.vcs.webhook_db import WebhookDatabase


class _FakeResponse:
    def __init__(self, status_code=200, text="", json_payload=None):
        self.status_code = status_code
        self.text = text
        self._json_payload = json_payload

    def json(self):
        if self._json_payload is not None:
            return self._json_payload
        raise ValueError("No JSON payload configured")


class _FakeClient:
    def __init__(self, *, get_responses=None, post_responses=None, patch_responses=None):
        self.get_calls = []
        self.post_calls = []
        self.patch_calls = []
        self.get_responses = get_responses or {}
        self.post_responses = post_responses or {}
        self.patch_responses = patch_responses or {}

    @staticmethod
    def _resolve_response(url, responses):
        for needle, response in responses.items():
            if needle in url:
                return response
        return _FakeResponse(status_code=200)

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self._resolve_response(url, self.post_responses)

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if "/labels" in url and not self.get_responses:
            return _FakeResponse(status_code=200, json_payload=[])
        return self._resolve_response(url, self.get_responses)

    async def patch(self, url, **kwargs):
        self.patch_calls.append((url, kwargs))
        return self._resolve_response(url, self.patch_responses)

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


@pytest.mark.asyncio
async def test_pr_opened_updates_status_with_cardstatus_enum(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")

    from orket.schema import CardStatus
    import orket.orchestration.engine as engine_module

    captured = {"status": None, "issue_id": None}
    scheduled: list[asyncio.Task] = []
    real_create_task = asyncio.create_task

    class _FakeCards:
        async def update_status(self, issue_id, status):
            captured["issue_id"] = issue_id
            captured["status"] = status

    class _FakeEngine:
        def __init__(self, _workspace):
            self.cards = _FakeCards()

        async def run_card(self, _issue_id):
            return None

    def _fake_create_task(coro):
        task = real_create_task(coro)
        scheduled.append(task)
        return task

    monkeypatch.setattr(engine_module, "OrchestrationEngine", _FakeEngine)
    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)

    handler = GiteaWebhookHandler(workspace=tmp_path)
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 12,
            "title": "[ISSUE-ABC123] add validation",
        },
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    result = await handler.handle_webhook("pull_request", payload)
    await handler.close()
    if scheduled:
        await asyncio.gather(*scheduled)

    assert result["status"] == "success"
    assert captured["issue_id"] == "ISSUE-ABC123"
    assert captured["status"] == CardStatus.CODE_REVIEW


@pytest.mark.asyncio
async def test_pr_review_approved_triggers_auto_merge(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.client = _FakeClient()

    payload = {
        "pull_request": {"number": 7},
        "review": {"user": {"login": "guard"}, "state": "approved"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    result = await handler.handle_webhook("pull_request_review", payload)
    await handler.close()

    assert result["status"] == "success"
    assert any("/pulls/7/merge" in call[0] for call in handler.client.post_calls)


@pytest.mark.asyncio
async def test_pr_review_approved_reports_merge_failure(monkeypatch, tmp_path):
    """Layer: integration. Verifies approved reviews do not claim merge success when the merge API fails."""
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.client = _FakeClient(
        post_responses={"/pulls/7/merge": _FakeResponse(status_code=409, text="merge conflict")},
    )

    payload = {
        "pull_request": {"number": 7},
        "review": {"user": {"login": "guard"}, "state": "approved"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    result = await handler.handle_webhook("pull_request_review", payload)
    await handler.close()

    assert result["status"] == "error"
    assert "merge failed" in result["message"].lower()
    assert "409" in result["message"]


@pytest.mark.asyncio
async def test_pr_review_commented_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.client = _FakeClient()

    payload = {
        "pull_request": {"number": 8},
        "review": {"user": {"login": "guard"}, "state": "commented"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    result = await handler.handle_webhook("pull_request_review", payload)
    await handler.close()

    assert result["status"] == "ignored"
    assert result["message"] == "Review state not actionable"


@pytest.mark.asyncio
async def test_pr_opened_without_issue_id_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")

    handler = GiteaWebhookHandler(workspace=tmp_path)
    payload = {
        "action": "opened",
        "pull_request": {"number": 9, "title": "no issue token"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    result = await handler.handle_webhook("pull_request", payload)
    await handler.close()

    assert result["status"] == "ignored"
    assert "No issue ID found" in result["message"]


@pytest.mark.asyncio
async def test_pr_review_escalation_failure_is_reported(monkeypatch, tmp_path):
    """Layer: integration. Verifies architect escalation reports comment publication failures instead of success."""
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "escalation_failure.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = _FakeClient(
        post_responses={"/issues/42/comments": _FakeResponse(status_code=500, text="comment blocked")},
    )

    payload = {
        "pull_request": {"number": 42},
        "review": {"user": {"login": "bot"}, "state": "changes_requested", "body": "still failing"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    await handler.handle_webhook("pull_request_review", payload)
    await handler.handle_webhook("pull_request_review", payload)
    result = await handler.handle_webhook("pull_request_review", payload)
    await handler.close()

    assert result["status"] == "error"
    assert "escalation failed" in result["message"].lower()
    assert "500" in result["message"]


@pytest.mark.asyncio
async def test_pr_merged_closes_cycle_and_skips_sandbox_deployment_with_explicit_reason(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "merged_test.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = _FakeClient()

    await handler.db.increment_pr_cycle("org/repo", 11)

    async def _raise_if_called(**_kwargs):
        raise AssertionError("sandbox creation should be skipped for merged webhook events")

    handler.sandbox_orchestrator.create_sandbox = _raise_if_called

    payload = {
        "action": "closed",
        "pull_request": {
            "number": 11,
            "merged": True,
            "head": {"ref": "main"},
            "merged_by": {"login": "guard"},
        },
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    result = await handler.handle_webhook("pull_request", payload)

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute("SELECT status FROM pr_review_cycles WHERE pr_key = ?", ("org/repo#11",))).fetchone()

    await handler.close()

    assert result["status"] == "skipped"
    assert "sandbox deployment skipped" in result["message"].lower()
    assert row["status"] == "merged"
    assert not any("/issues/11/comments" in call[0] for call in handler.client.post_calls)


@pytest.mark.asyncio
async def test_pr_merged_skip_does_not_attempt_sandbox_creation(monkeypatch, tmp_path):
    """Layer: integration. Verifies merged PR handling explicitly skips unsupported sandbox deployment instead of attempting a failing deploy."""
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "merged_failure.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = _FakeClient()

    await handler.db.increment_pr_cycle("org/repo", 12)

    async def _raise_create_sandbox(**_kwargs):
        raise AssertionError("sandbox creation should not be attempted")

    handler.sandbox_orchestrator.create_sandbox = _raise_create_sandbox

    payload = {
        "action": "closed",
        "pull_request": {
            "number": 12,
            "merged": True,
            "head": {"ref": "main"},
            "merged_by": {"login": "guard"},
        },
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    result = await handler.handle_webhook("pull_request", payload)

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute("SELECT status FROM pr_review_cycles WHERE pr_key = ?", ("org/repo#12",))).fetchone()

    await handler.close()

    assert result["status"] == "skipped"
    assert "not yet positioned to produce deployable code projects" in result["message"].lower()
    assert row["status"] == "merged"


@pytest.mark.asyncio
async def test_auto_reject_creates_requirements_review_issue(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "requirements_issue_test.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = _FakeClient(
        get_responses={
            "/labels": _FakeResponse(
                status_code=200,
                json_payload=[
                    {"id": 11, "name": "requirements-review"},
                    {"id": 12, "name": "auto-rejected"},
                ],
            )
        }
    )

    payload = {
        "pull_request": {"number": 21},
        "review": {"user": {"login": "guard"}, "state": "changes_requested", "body": "still failing"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    for _ in range(4):
        await handler.handle_webhook("pull_request_review", payload)

    await handler.close()

    issue_call = next(call for call in handler.client.post_calls if call[0].endswith("/api/v1/repos/org/repo/issues"))
    assert issue_call[1]["json"]["labels"] == [11, 12]


@pytest.mark.asyncio
async def test_auto_reject_creates_unlabeled_requirements_issue_when_repo_labels_missing(monkeypatch, tmp_path):
    """Layer: integration. Verifies auto-reject still creates the follow-up issue when the repo does not define the expected labels."""
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "requirements_issue_missing_labels.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = _FakeClient(
        get_responses={"/labels": _FakeResponse(status_code=200, json_payload=[])},
    )

    payload = {
        "pull_request": {"number": 22},
        "review": {"user": {"login": "guard"}, "state": "changes_requested", "body": "still failing"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    for _ in range(4):
        result = await handler.handle_webhook("pull_request_review", payload)

    await handler.close()

    issue_call = next(call for call in handler.client.post_calls if call[0].endswith("/api/v1/repos/org/repo/issues"))
    assert result["status"] == "rejected"
    assert "labels" not in issue_call[1]["json"]


@pytest.mark.asyncio
async def test_auto_reject_reports_close_failure_without_marking_rejected(monkeypatch, tmp_path):
    """Layer: integration. Verifies auto-reject stops and reports failure when the PR close request fails."""
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    db_path = tmp_path / "reject_failure.db"

    handler = GiteaWebhookHandler(workspace=tmp_path)
    handler.db = WebhookDatabase(db_path=db_path)
    handler.client = _FakeClient(
        patch_responses={"/pulls/55": _FakeResponse(status_code=503, text="gitea unavailable")},
    )

    payload = {
        "pull_request": {"number": 55},
        "review": {"user": {"login": "guard"}, "state": "changes_requested", "body": "still failing"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
    }

    for _ in range(3):
        interim = await handler.handle_webhook("pull_request_review", payload)
        assert interim["status"] in {"changes_requested", "escalated"}
    result = await handler.handle_webhook("pull_request_review", payload)

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute("SELECT status FROM pr_review_cycles WHERE pr_key = ?", ("org/repo#55",))).fetchone()

    await handler.close()

    assert result["status"] == "error"
    assert "rejection failed" in result["message"].lower()
    assert "503" in result["message"]
    assert row["status"] == "active"
