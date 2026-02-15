from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.adapters.storage.gitea_state_models import CardSnapshot, encode_snapshot
from orket.application.services.gitea_state_worker import GiteaStateWorker


class _SimResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _Store:
    def __init__(self):
        self.issue_number = 501
        self.snapshot = CardSnapshot(card_id="ISSUE-501", state="ready", version=1)
        self.etag_version = 1
        self.comments = []

    def get_issue(self):
        return _SimResponse(
            {"number": self.issue_number, "body": encode_snapshot(self.snapshot)},
            headers={"ETag": f'"v{self.etag_version}"'},
        )

    def patch_issue(self, payload, if_match):
        expected = f'"v{self.etag_version}"'
        if if_match and if_match != expected:
            raise ValueError("etag_conflict")
        from orket.adapters.storage.gitea_state_models import decode_snapshot

        self.snapshot = decode_snapshot(payload["body"])
        self.etag_version += 1
        return _SimResponse({"ok": True})

    def list_comments(self):
        return _SimResponse(self.comments)

    def add_comment(self, payload):
        self.comments.append({"body": payload["body"]})
        return _SimResponse({"id": len(self.comments)})


def _wire(adapter: GiteaStateAdapter, store: _Store):
    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        if method == "GET" and path == f"/issues/{store.issue_number}":
            return store.get_issue()
        raise AssertionError(f"unexpected request_response: {method} {path}")

    async def fake_request_json(method, path, *, params=None, payload=None, extra_headers=None):
        if method == "GET" and path == "/issues":
            return [{"number": store.issue_number, "body": encode_snapshot(store.snapshot)}]
        if method == "PATCH" and path == f"/issues/{store.issue_number}":
            try:
                return store.patch_issue(payload, (extra_headers or {}).get("If-Match")).json()
            except ValueError as exc:
                from orket.adapters.storage.gitea_state_adapter import GiteaAdapterConflictError

                raise GiteaAdapterConflictError(str(exc)) from exc
        if method == "GET" and path == f"/issues/{store.issue_number}/comments":
            return store.list_comments().json()
        if method == "POST" and path == f"/issues/{store.issue_number}/comments":
            return store.add_comment(payload).json()
        raise AssertionError(f"unexpected request_json: {method} {path}")

    adapter._request_response = fake_request_response  # type: ignore[method-assign]
    adapter._request_json = fake_request_json  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_multi_runner_lease_lifecycle_with_renew_and_takeover(monkeypatch):
    store = _Store()
    runner_a = GiteaStateAdapter(base_url="https://gitea.local", owner="acme", repo="orket", token="x")
    runner_b = GiteaStateAdapter(base_url="https://gitea.local", owner="acme", repo="orket", token="x")
    _wire(runner_a, store)
    _wire(runner_b, store)

    clock = {"now": datetime(2026, 2, 15, 12, 0, tzinfo=UTC)}
    monkeypatch.setattr(runner_a, "_now_utc", lambda: clock["now"])
    monkeypatch.setattr(runner_b, "_now_utc", lambda: clock["now"])

    lease_a = await runner_a.acquire_lease(str(store.issue_number), owner_id="runner-a", lease_seconds=5)
    assert lease_a is not None
    assert lease_a["lease"]["owner_id"] == "runner-a"
    assert lease_a["lease"]["epoch"] == 1

    # Competing runner cannot acquire while lease is active.
    clock["now"] = clock["now"] + timedelta(seconds=2)
    blocked_b = await runner_b.acquire_lease(str(store.issue_number), owner_id="runner-b", lease_seconds=5)
    assert blocked_b is None

    # Owner renews lease before expiration.
    renewed_a = await runner_a.renew_lease(str(store.issue_number), owner_id="runner-a", lease_seconds=5)
    assert renewed_a is not None
    assert renewed_a["lease"]["epoch"] == 1

    # Still active: competing runner remains blocked.
    clock["now"] = clock["now"] + timedelta(seconds=4)
    still_blocked_b = await runner_b.acquire_lease(str(store.issue_number), owner_id="runner-b", lease_seconds=5)
    assert still_blocked_b is None

    # After expiry: takeover succeeds and epoch advances.
    clock["now"] = clock["now"] + timedelta(seconds=3)
    takeover_b = await runner_b.acquire_lease(str(store.issue_number), owner_id="runner-b", lease_seconds=5)
    assert takeover_b is not None
    assert takeover_b["lease"]["owner_id"] == "runner-b"
    assert takeover_b["lease"]["epoch"] >= 2


@pytest.mark.asyncio
async def test_worker_takeover_after_expired_foreign_lease(monkeypatch):
    store = _Store()
    adapter_a = GiteaStateAdapter(base_url="https://gitea.local", owner="acme", repo="orket", token="x")
    adapter_b = GiteaStateAdapter(base_url="https://gitea.local", owner="acme", repo="orket", token="x")
    _wire(adapter_a, store)
    _wire(adapter_b, store)

    worker_b = GiteaStateWorker(
        adapter=adapter_b,
        worker_id="runner-b",
        lease_seconds=5,
        renew_interval_seconds=0.1,
    )

    # Runner A claims lease and then disappears without processing.
    lease_a = await adapter_a.acquire_lease(str(store.issue_number), owner_id="runner-a", lease_seconds=5)
    assert lease_a is not None
    blocked = await worker_b.run_once(work_fn=lambda _c: _noop_result())
    assert blocked is False

    # Force lease expiry; worker B should now be able to process.
    store.snapshot.lease.expires_at = "2024-01-01T00:00:00+00:00"
    processed = await worker_b.run_once(work_fn=lambda _c: _noop_result())
    assert processed is True
    assert str(store.snapshot.lease.owner_id or "") == ""
    assert store.snapshot.state == "code_review"


async def _noop_result():
    return {"ok": True}
