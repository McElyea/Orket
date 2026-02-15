import pytest
import httpx

from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.adapters.storage.gitea_state_models import CardSnapshot, encode_snapshot


@pytest.mark.asyncio
async def test_fetch_ready_cards_ignores_non_orket_issues(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    snapshot_body = encode_snapshot(CardSnapshot(card_id="ISSUE-1", state="ready", version=2))
    fake_issues = [
        {"number": 1, "body": snapshot_body},
        {"number": 2, "body": "plain issue body"},
    ]

    async def fake_request_json(method, path, *, params=None, payload=None):
        assert method == "GET"
        assert path == "/issues"
        assert params["labels"] == "status/ready"
        return fake_issues

    monkeypatch.setattr(adapter, "_request_json", fake_request_json)
    cards = await adapter.fetch_ready_cards(limit=5)

    assert len(cards) == 1
    assert cards[0]["card_id"] == "ISSUE-1"
    assert cards[0]["issue_number"] == 1
    assert cards[0]["version"] == 2


@pytest.mark.asyncio
async def test_append_event_posts_orket_comment(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    captured = {}

    async def fake_request_json(method, path, *, params=None, payload=None):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        return {"id": 1}

    monkeypatch.setattr(adapter, "_request_json", fake_request_json)
    await adapter.append_event("7", event_type="guard_failure", payload={"code": "HALLUCINATION"})

    assert captured["method"] == "POST"
    assert captured["path"] == "/issues/7/comments"
    assert captured["payload"]["body"].startswith("[ORKET_EVENT_V1]")


@pytest.mark.asyncio
async def test_append_event_with_idempotency_key_skips_duplicate(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    captured = {"calls": []}

    async def fake_request_json(method, path, *, params=None, payload=None, extra_headers=None):
        captured["calls"].append((method, path, payload))
        if method == "GET":
            return [{"body": '[ORKET_EVENT_V1] {"created_at":"2026-02-15T10:00:00+00:00","event_type":"guard_failure","idempotency_key":"evt-1","payload":{"idempotency_key":"evt-1"}}'}]
        raise AssertionError("POST should not happen when idempotency key already exists.")

    monkeypatch.setattr(adapter, "_request_json", fake_request_json)
    await adapter.append_event(
        "7",
        event_type="guard_failure",
        payload={"code": "HALLUCINATION", "idempotency_key": "evt-1"},
    )
    assert captured["calls"] == [("GET", "/issues/7/comments", None)]


@pytest.mark.asyncio
async def test_append_event_with_idempotency_key_posts_when_missing(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    captured = {"calls": []}

    async def fake_request_json(method, path, *, params=None, payload=None, extra_headers=None):
        captured["calls"].append((method, path, payload))
        if method == "GET":
            return []
        return {"id": 1}

    monkeypatch.setattr(adapter, "_request_json", fake_request_json)
    await adapter.append_event(
        "9",
        event_type="guard_failure",
        payload={"code": "HALLUCINATION", "idempotency_key": "evt-2"},
    )
    assert captured["calls"][0] == ("GET", "/issues/9/comments", None)
    assert captured["calls"][1][0] == "POST"
    assert captured["calls"][1][1] == "/issues/9/comments"
    assert "evt-2" in captured["calls"][1][2]["body"]


@pytest.mark.asyncio
async def test_unimplemented_mutating_operations_are_explicit():
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    with pytest.raises(NotImplementedError):
        await adapter.release_or_fail("1", final_state="failed", error="boom")


@pytest.mark.asyncio
async def test_transition_state_uses_canonical_state_machine_validation():
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    with pytest.raises(ValueError, match="Invalid state transition"):
        await adapter.transition_state("1", from_state="done", to_state="in_progress")


@pytest.mark.asyncio
async def test_transition_state_persists_with_if_match(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    body = encode_snapshot(CardSnapshot(card_id="ISSUE-10", state="ready", version=1))
    captured = {}

    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        assert method == "GET"
        assert path == "/issues/10"
        return _FakeResponse({"number": 10, "body": body}, headers={"ETag": '"v1"'})

    async def fake_request_json(method, path, *, params=None, payload=None, extra_headers=None):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        captured["headers"] = extra_headers
        return {"ok": True}

    monkeypatch.setattr(adapter, "_request_response", fake_request_response)
    monkeypatch.setattr(adapter, "_request_json", fake_request_json)
    await adapter.transition_state("10", from_state="ready", to_state="in_progress", reason="start work")

    assert captured["method"] == "PATCH"
    assert captured["path"] == "/issues/10"
    assert captured["headers"] == {"If-Match": '"v1"'}
    assert '"state":"in_progress"' in captured["payload"]["body"]
    assert '"transition_reason":"start work"' in captured["payload"]["body"]


@pytest.mark.asyncio
async def test_transition_state_rejects_stale_from_state(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    body = encode_snapshot(CardSnapshot(card_id="ISSUE-11", state="code_review", version=4))

    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        return _FakeResponse({"number": 11, "body": body}, headers={"ETag": '"v4"'})

    monkeypatch.setattr(adapter, "_request_response", fake_request_response)
    with pytest.raises(ValueError, match="Stale transition rejected"):
        await adapter.transition_state("11", from_state="ready", to_state="in_progress")


@pytest.mark.asyncio
async def test_transition_state_is_idempotent_when_target_state_already_applied(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    body = encode_snapshot(CardSnapshot(card_id="ISSUE-11A", state="in_progress", version=5))

    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        return _FakeResponse({"number": 111, "body": body}, headers={"ETag": '"v5"'})

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("PATCH should not happen for idempotent duplicate transition.")

    monkeypatch.setattr(adapter, "_request_response", fake_request_response)
    monkeypatch.setattr(adapter, "_request_json", fail_if_called)
    await adapter.transition_state("111", from_state="ready", to_state="in_progress")


@pytest.mark.asyncio
async def test_transition_state_rejects_etag_conflict(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    body = encode_snapshot(CardSnapshot(card_id="ISSUE-12", state="ready", version=5))

    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        return _FakeResponse({"number": 12, "body": body}, headers={"ETag": '"v5"'})

    async def fake_request_json(method, path, *, params=None, payload=None, extra_headers=None):
        request = httpx.Request("PATCH", "https://gitea.local/api/v1/repos/acme/orket/issues/12")
        response = httpx.Response(409, request=request)
        raise httpx.HTTPStatusError("conflict", request=request, response=response)

    monkeypatch.setattr(adapter, "_request_response", fake_request_response)
    monkeypatch.setattr(adapter, "_request_json", fake_request_json)
    with pytest.raises(ValueError, match="compare-and-swap conflict"):
        await adapter.transition_state("12", from_state="ready", to_state="in_progress")


class _FakeResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_acquire_lease_claims_unowned_card_with_epoch_increment(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    body = encode_snapshot(CardSnapshot(card_id="ISSUE-5", state="ready", version=3))
    captured = {}

    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        assert method == "GET"
        assert path == "/issues/5"
        return _FakeResponse({"number": 5, "body": body}, headers={"ETag": '"v3"'})

    async def fake_request_json(method, path, *, params=None, payload=None, extra_headers=None):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        captured["headers"] = extra_headers
        return {"ok": True}

    monkeypatch.setattr(adapter, "_request_response", fake_request_response)
    monkeypatch.setattr(adapter, "_request_json", fake_request_json)
    lease = await adapter.acquire_lease("5", owner_id="runner-a", lease_seconds=30)

    assert lease is not None
    assert lease["card_id"] == "ISSUE-5"
    assert lease["version"] == 4
    assert lease["lease"]["owner_id"] == "runner-a"
    assert lease["lease"]["epoch"] == 1
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/issues/5"
    assert captured["headers"] == {"If-Match": '"v3"'}


@pytest.mark.asyncio
async def test_acquire_lease_returns_none_when_another_owner_has_active_lease(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    body = encode_snapshot(
        CardSnapshot(
            card_id="ISSUE-6",
            state="ready",
            version=2,
            lease={"owner_id": "runner-b", "acquired_at": "2026-02-15T10:00:00+00:00", "expires_at": "3026-02-15T10:00:00+00:00", "epoch": 9},
        )
    )

    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        return _FakeResponse({"number": 6, "body": body}, headers={"ETag": '"v2"'})

    monkeypatch.setattr(adapter, "_request_response", fake_request_response)
    lease = await adapter.acquire_lease("6", owner_id="runner-a", lease_seconds=30)
    assert lease is None


@pytest.mark.asyncio
async def test_acquire_lease_is_idempotent_for_same_owner(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    body = encode_snapshot(
        CardSnapshot(
            card_id="ISSUE-7",
            state="ready",
            version=8,
            lease={"owner_id": "runner-a", "acquired_at": "2026-02-15T10:00:00+00:00", "expires_at": "3026-02-15T10:00:00+00:00", "epoch": 3},
        )
    )

    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        return _FakeResponse({"number": 7, "body": body}, headers={"ETag": '"v8"'})

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("PATCH should not be called for idempotent same-owner lease acquire.")

    monkeypatch.setattr(adapter, "_request_response", fake_request_response)
    monkeypatch.setattr(adapter, "_request_json", fail_if_called)
    lease = await adapter.acquire_lease("7", owner_id="runner-a", lease_seconds=30)
    assert lease is not None
    assert lease["version"] == 8
    assert lease["lease"]["epoch"] == 3


@pytest.mark.asyncio
async def test_acquire_lease_returns_none_on_etag_conflict(monkeypatch):
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    body = encode_snapshot(CardSnapshot(card_id="ISSUE-8", state="ready", version=1))

    async def fake_request_response(method, path, *, params=None, payload=None, extra_headers=None):
        return _FakeResponse({"number": 8, "body": body}, headers={"ETag": '"v1"'})

    async def fake_request_json(method, path, *, params=None, payload=None, extra_headers=None):
        request = httpx.Request("PATCH", "https://gitea.local/api/v1/repos/acme/orket/issues/8")
        response = httpx.Response(412, request=request)
        raise httpx.HTTPStatusError("precondition failed", request=request, response=response)

    monkeypatch.setattr(adapter, "_request_response", fake_request_response)
    monkeypatch.setattr(adapter, "_request_json", fake_request_json)
    lease = await adapter.acquire_lease("8", owner_id="runner-a", lease_seconds=30)
    assert lease is None
