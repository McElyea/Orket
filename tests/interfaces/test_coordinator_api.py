from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from orket.core.domain.coordinator_card import Card
from orket.interfaces.coordinator_api import app, store


client = TestClient(app)


def _card(*, state: str, claimed_by: str | None = None, lease_expires_at: float | None = None) -> Card:
    return Card(
        id="card-1",
        payload={"task": "demo"},
        state=state,
        claimed_by=claimed_by,
        lease_expires_at=lease_expires_at,
        result=None,
        attempts=0,
        hedged_execution=False,
    )


@pytest.mark.parametrize(
    ("cards", "path", "payload", "expected_status", "expected_detail"),
    [
        ([], "/cards/missing-card/claim", {"node_id": "worker-a", "lease_duration": 1.0}, 404, "card not found"),
        ([_card(state="OPEN")], "/cards/card-1/claim", {"node_id": "worker-a", "lease_duration": 0}, 400, "lease_duration must be > 0"),
        (
            [_card(state="CLAIMED", claimed_by="worker-a", lease_expires_at=time.monotonic() + 60.0)],
            "/cards/card-1/renew",
            {"node_id": "worker-b", "lease_duration": 1.0},
            403,
            "only claimant may renew",
        ),
        ([_card(state="DONE")], "/cards/card-1/claim", {"node_id": "worker-a", "lease_duration": 1.0}, 409, "card is finalized"),
    ],
)
def test_coordinator_api_maps_store_errors_to_http_responses(
    cards: list[Card],
    path: str,
    payload: dict[str, object],
    expected_status: int,
    expected_detail: str,
) -> None:
    """Layer: contract. Verifies coordinator API translates coordinator store errors at the HTTP boundary."""
    store.reset(cards)

    response = client.post(path, json=payload)

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
