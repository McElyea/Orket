from __future__ import annotations

import pytest

import orket.vendors.gitea as gitea_module
from orket.vendors.gitea import GiteaVendor


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.is_success = True

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, capture: dict, *, get_payload=None, post_payload=None):
        self._capture = capture
        self._get_payload = get_payload if get_payload is not None else []
        self._post_payload = post_payload if post_payload is not None else {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None, params=None):
        self._capture["get"] = {"url": url, "headers": headers, "params": params}
        return _FakeResponse(self._get_payload)

    async def post(self, url, headers=None, json=None):
        self._capture["post"] = {"url": url, "headers": headers, "json": json}
        return _FakeResponse(self._post_payload)


@pytest.mark.asyncio
async def test_get_cards_rejects_non_numeric_epic_id():
    vendor = GiteaVendor("https://gitea.example.com", "token", "owner", "repo")
    with pytest.raises(ValueError, match="epic_id must be an integer label id"):
        await vendor.get_cards(epic_id="label-name")


@pytest.mark.asyncio
async def test_add_card_rejects_non_numeric_epic_id():
    vendor = GiteaVendor("https://gitea.example.com", "token", "owner", "repo")
    with pytest.raises(ValueError, match="epic_id must be an integer label id"):
        await vendor.add_card(epic_id="label-name", summary="x", description="y")


@pytest.mark.asyncio
async def test_get_cards_uses_normalized_label_param(monkeypatch):
    capture: dict = {}
    fake_payload = [{"number": 7, "title": "Issue 7", "body": "Body", "state": "open"}]

    monkeypatch.setattr(
        gitea_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeClient(capture, get_payload=fake_payload),
    )
    vendor = GiteaVendor("https://gitea.example.com", "token", "owner", "repo")

    cards = await vendor.get_cards(epic_id="42")

    assert len(cards) == 1
    assert cards[0].id == "7"
    assert capture["get"]["params"] == {"labels": "42"}


@pytest.mark.asyncio
async def test_add_card_uses_integer_label_id(monkeypatch):
    capture: dict = {}
    fake_payload = {"number": 8, "title": "Issue 8"}

    monkeypatch.setattr(
        gitea_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeClient(capture, post_payload=fake_payload),
    )
    vendor = GiteaVendor("https://gitea.example.com", "token", "owner", "repo")

    card = await vendor.add_card(epic_id="12", summary="Issue 8", description="Body")

    assert card.id == "8"
    assert capture["post"]["json"]["labels"] == [12]
