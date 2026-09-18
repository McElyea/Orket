from __future__ import annotations

import pytest
from fastapi import HTTPException

from orket.application.services.coordinator_store import CoordinatorNotFoundError, InMemoryCoordinatorStore
from orket.core.domain.coordinator_card import Card


def test_claim_missing_card_raises_service_error_not_http_exception() -> None:
    """Layer: unit. Verifies coordinator store failures stay out of the FastAPI transport layer."""
    store = InMemoryCoordinatorStore()
    store.reset([])

    with pytest.raises(CoordinatorNotFoundError) as exc_info:
        store.claim("missing-card", "worker-a", 1.0)

    assert str(exc_info.value) == "card not found"
    assert not isinstance(exc_info.value, HTTPException)


@pytest.mark.unit
@pytest.mark.parametrize("kind", ["complete", "fail"])
def test_terminal_result_does_not_retain_caller_alias(kind):
    store = InMemoryCoordinatorStore(monotonic_factory=lambda: 1000.0)
    store.reset([Card(id="card", payload={}, state="OPEN", hedged_execution=False)])
    store.claim("card", "node", 10)
    submitted = {"nested": {"status": "captured"}}
    method = store.complete if kind == "complete" else store.fail
    result = method("card", "node", submitted)
    submitted["nested"]["status"] = "changed-after-return"
    assert result.result == store.snapshot_card("card").result == {"nested": {"status": "captured"}}
