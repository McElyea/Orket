"""Real ASGI/SQLite ingress; held workers are controlled interruption evidence."""

import asyncio
import hashlib
import hmac
import sqlite3
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from orket.adapters.execution.owned_io import run_owned_thread
from tests.helpers.webhook import application, signed

pytestmark = pytest.mark.integration


def review_payload(**extra):
    return {
        "pull_request": {"number": 7},
        "review": {"user": {"login": "reviewer"}, "state": "changes_requested", "body": "Fix validation"},
        "repository": {"name": "repo", "owner": {"login": "org"}},
        **extra,
    }


def test_signed_delivery_identity_survives_transport_and_restart(tmp_path):
    payload = review_payload()
    app = application(tmp_path)
    with TestClient(app) as client:
        first = signed(client, payload, event="pull_request_review", delivery="delivery-one")
        duplicate = signed(client, payload, event="pull_request_review", delivery="delivery-one")
        assert first.json()["status"] == "changes_requested"
        assert duplicate.json()["status"] == "duplicate"
        db_path = app.state.webhook_runtime.db.db_path
    with TestClient(application(tmp_path)) as client:
        assert (
            signed(client, payload, event="pull_request_review", delivery="delivery-one").json()["status"]
            == "duplicate"
        )
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT cycle_count FROM pr_review_cycles").fetchall() == [(1,)]
        assert connection.execute("SELECT event_id FROM webhook_event_dedupe").fetchall() == [("delivery-one",)]
        assert connection.execute("SELECT count(*) FROM review_failures").fetchone() == (1,)


@pytest.mark.parametrize("field", ["event_id", "delivery_id", "x_gitea_delivery", "X-Gitea-Delivery"])
def test_payload_delivery_identity_is_preserved_and_conflicts_refused(tmp_path, field):
    app = application(tmp_path)
    payload = review_payload(**{field: "payload-delivery"})
    with TestClient(app) as client:
        conflict = signed(client, payload, event="pull_request_review", delivery="conflicting-header")
        assert conflict.status_code == 400
        assert not app.state.webhook_runtime.db.db_path.exists()
        first = signed(client, payload, event="pull_request_review")
        second = signed(client, payload, event="pull_request_review")
        assert first.json()["status"] == "changes_requested" and second.json()["status"] == "duplicate"


def test_signed_malformed_or_oversized_body_is_refused_before_dispatch(tmp_path):
    app = application(tmp_path)
    with TestClient(app) as client:
        assert signed(client, {"number": -1}, event="pull_request").status_code == 400
        body = b"x" * (1024 * 1024 + 1)
        digest = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        assert client.post("/webhook/gitea", content=body, headers={"X-Gitea-Signature": digest}).status_code == 413
        assert not app.state.webhook_runtime.db.db_path.exists()


@pytest.mark.parametrize("fault", ["wrong-event", "mixed-vocabulary", "unknown-review", "missing-sender"])
def test_native_review_refuses_ambiguous_or_incomplete_wire_values(tmp_path, fault):
    payload = review_payload(action="reviewed", sender={"login": "reviewer"})
    payload["review"] = {"type": "pull_request_review_rejected", "content": "Fix validation"}
    event = "pull_request_rejected"
    if fault == "wrong-event":
        event = "pull_request_approved"
    elif fault == "mixed-vocabulary":
        payload["review"]["state"] = "approved"
    elif fault == "unknown-review":
        payload["review"]["type"] = "unknown"
    else:
        del payload["sender"]
    app = application(tmp_path)
    with TestClient(app) as client:
        response = signed(client, payload, event=event)
        assert response.status_code == 200
        assert response.json()["error"] == "webhook_payload_validation_failed"
        assert not app.state.webhook_runtime.db.db_path.exists()


@pytest.mark.asyncio
async def test_http_disconnect_and_shutdown_retain_admitted_file_worker(tmp_path, monkeypatch):
    app = application(tmp_path)
    entered, release = threading.Event(), threading.Event()
    marker = tmp_path / "worker-finished.txt"

    def held_file_effect():
        entered.set()
        assert release.wait(5), "Test must release its admitted file worker"
        marker.write_text("finished", encoding="utf-8")

    async with app.router.lifespan_context(app):
        runtime = app.state.webhook_runtime
        original_log = runtime._log_event

        async def held_log(name, payload):
            await run_owned_thread(held_file_effect, label="webhook-held-log-test")
            await original_log(name, payload)

        monkeypatch.setattr(runtime, "_log_event", held_log)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            request = asyncio.create_task(client.post("/webhook/gitea", json={}))
            closing = None
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                request.cancel()
                closing = asyncio.create_task(runtime.close())
                await asyncio.sleep(0)
                closing.cancel()
                await asyncio.sleep(0)
                closing.cancel()
                assert not request.done() and not closing.done() and not runtime.client.is_closed
                assert (await client.get("/health")).status_code == 503
                release.set()
                await asyncio.gather(request, closing, return_exceptions=True)
                assert runtime.closed and runtime.client.is_closed
                assert await asyncio.to_thread(marker.read_text, encoding="utf-8") == "finished"
            finally:
                release.set()
                await asyncio.gather(request, *([closing] if closing else []), return_exceptions=True)


@pytest.mark.asyncio
async def test_direct_dispatch_captures_nested_payload_before_first_await(tmp_path, monkeypatch):
    app = application(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    payload = review_payload()
    async with app.router.lifespan_context(app):
        runtime = app.state.webhook_runtime
        original_dispatch = runtime._dispatch

        async def held_dispatch(event, captured):
            entered.set()
            await release.wait()
            return await original_dispatch(event, captured)

        monkeypatch.setattr(runtime, "_dispatch", held_dispatch)
        request = asyncio.create_task(runtime.handle_webhook("pull_request_review", payload))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            payload["review"]["state"] = "approved"
            payload["repository"]["name"] = "changed"
            release.set()
            result = await request
            assert result["status"] == "changes_requested"
            assert await runtime.db.get_pr_cycle_count("org/repo", 7) == 1
            assert await runtime.db.get_pr_cycle_count("org/changed", 7) == 0
        finally:
            release.set()
            await asyncio.gather(request, return_exceptions=True)
