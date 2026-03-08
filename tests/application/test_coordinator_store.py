from __future__ import annotations

import pytest
from fastapi import HTTPException

from orket.application.services.coordinator_store import CoordinatorNotFoundError, InMemoryCoordinatorStore


def test_claim_missing_card_raises_service_error_not_http_exception() -> None:
    """Layer: unit. Verifies coordinator store failures stay out of the FastAPI transport layer."""
    store = InMemoryCoordinatorStore()
    store.reset([])

    with pytest.raises(CoordinatorNotFoundError) as exc_info:
        store.claim("missing-card", "worker-a", 1.0)

    assert str(exc_info.value) == "card not found"
    assert not isinstance(exc_info.value, HTTPException)
