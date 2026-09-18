from __future__ import annotations

import time

import pytest

from orket.core.domain.coordinator_card import Card
from tests.helpers.coordinator import coordinator_sqlite as coordinator_sqlite

pytestmark = pytest.mark.integration


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
    ("cards_factory", "path", "payload", "expected_status", "expected_detail"),
    [
        (lambda: [], "/cards/missing-card/claim", {"node_id": "worker-a", "lease_duration": 1.0}, 404, "card not found"),
        (lambda: [_card(state="OPEN")], "/cards/card-1/claim", {"node_id": "worker-a", "lease_duration": 0}, 400, "lease_duration must be > 0"),
        (
            lambda: [_card(state="CLAIMED", claimed_by="worker-a", lease_expires_at=time.monotonic() + 60.0)],
            "/cards/card-1/renew",
            {"node_id": "worker-b", "lease_duration": 1.0},
            403,
            "only claimant may renew",
        ),
        (lambda: [_card(state="DONE")], "/cards/card-1/claim", {"node_id": "worker-a", "lease_duration": 1.0}, 409, "card is finalized"),
    ],
)
def test_coordinator_api_maps_store_errors_to_http_responses(
    cards_factory,
    path: str,
    payload: dict[str, object],
    expected_status: int,
    expected_detail: str,
    coordinator_sqlite,
) -> None:
    """Layer: integration. Real standalone API maps application errors at the HTTP boundary."""
    coordinator_sqlite.owner.store.reset(cards_factory())

    response = coordinator_sqlite.client.post(path, json=payload)

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_coordinator_factory_does_not_seed_demo_cards(coordinator_sqlite) -> None:
    assert coordinator_sqlite.owner.store.list_open_cards() == []
