import pytest

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
async def test_unimplemented_mutating_operations_are_explicit():
    adapter = GiteaStateAdapter(
        base_url="https://gitea.local",
        owner="acme",
        repo="orket",
        token="secret",
    )
    with pytest.raises(NotImplementedError):
        await adapter.acquire_lease("1", owner_id="runner-a", lease_seconds=30)
    with pytest.raises(NotImplementedError):
        await adapter.transition_state("1", from_state="ready", to_state="in_progress")
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
