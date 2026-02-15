import json

import pytest

from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.adapters.storage.gitea_state_models import CardSnapshot, encode_snapshot


class _SimResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _FakeGiteaIssueStore:
    def __init__(self):
        self.issue_number = 100
        self.snapshot = CardSnapshot(card_id="ISSUE-100", state="ready", version=1)
        self.etag_version = 1
        self.comments = []

    def get_issue(self):
        return _SimResponse(
            {
                "number": self.issue_number,
                "body": encode_snapshot(self.snapshot),
            },
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


def _wire_adapter(adapter: GiteaStateAdapter, store: _FakeGiteaIssueStore):
    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        if method == "GET" and path == f"/issues/{store.issue_number}":
            return store.get_issue()
        raise AssertionError(f"Unexpected request_response call: {method} {path}")

    async def fake_request_json(method, path, *, params=None, payload=None, extra_headers=None):
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
        raise AssertionError(f"Unexpected request_json call: {method} {path}")

    adapter._request_response = fake_request_response  # type: ignore[method-assign]
    adapter._request_json = fake_request_json  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_two_runners_do_not_dual_acquire_active_lease():
    store = _FakeGiteaIssueStore()
    runner_a = GiteaStateAdapter(base_url="https://gitea.local", owner="acme", repo="orket", token="x")
    runner_b = GiteaStateAdapter(base_url="https://gitea.local", owner="acme", repo="orket", token="x")
    _wire_adapter(runner_a, store)
    _wire_adapter(runner_b, store)

    lease_a = await runner_a.acquire_lease(str(store.issue_number), owner_id="runner-a", lease_seconds=30)
    lease_b = await runner_b.acquire_lease(str(store.issue_number), owner_id="runner-b", lease_seconds=30)

    assert lease_a is not None
    assert lease_a["lease"]["owner_id"] == "runner-a"
    assert lease_b is None


@pytest.mark.asyncio
async def test_expired_lease_can_be_taken_over_by_second_runner():
    store = _FakeGiteaIssueStore()
    runner_a = GiteaStateAdapter(base_url="https://gitea.local", owner="acme", repo="orket", token="x")
    runner_b = GiteaStateAdapter(base_url="https://gitea.local", owner="acme", repo="orket", token="x")
    _wire_adapter(runner_a, store)
    _wire_adapter(runner_b, store)

    first = await runner_a.acquire_lease(str(store.issue_number), owner_id="runner-a", lease_seconds=1)
    assert first is not None
    # Force expiration in stored snapshot to simulate timeout-based takeover.
    store.snapshot.lease.expires_at = "2024-01-01T00:00:00+00:00"

    second = await runner_b.acquire_lease(str(store.issue_number), owner_id="runner-b", lease_seconds=30)
    assert second is not None
    assert second["lease"]["owner_id"] == "runner-b"
    assert second["lease"]["epoch"] >= 2
