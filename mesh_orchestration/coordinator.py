from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from mesh_orchestration.card import Card

app = FastAPI(title="Mesh Coordinator")


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    lease_seconds: int = 5


class RenewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    lease_seconds: int = 5


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    result: Any | None = None


class FailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    result: Any | None = None


class InMemoryCardStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cards: dict[str, Card] = {
            "demo-card-1": Card(
                id="demo-card-1",
                payload={"task": "simulate takeover", "duration_seconds": 8},
                state="OPEN",
                attempts=0,
            )
        }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _normalize_for_expiry(self, card: Card) -> Card:
        if (
            card.state == "CLAIMED"
            and card.lease_expires_at is not None
            and card.lease_expires_at < self._now()
        ):
            card.state = "OPEN"
            card.claimed_by = None
            card.lease_expires_at = None
        return card

    def list_cards(self, state_filter: str | None = None) -> list[Card]:
        with self._lock:
            cards: list[Card] = []
            for card in self._cards.values():
                self._normalize_for_expiry(card)
                if state_filter is None or card.state == state_filter:
                    cards.append(card.model_copy(deep=True))
            return cards

    def claim(self, card_id: str, node_id: str, lease_seconds: int) -> Card:
        if lease_seconds <= 0:
            raise HTTPException(status_code=400, detail="lease_seconds must be > 0")

        with self._lock:
            card = self._cards.get(card_id)
            if card is None:
                raise HTTPException(status_code=404, detail="card not found")

            self._normalize_for_expiry(card)
            if card.state != "OPEN":
                raise HTTPException(status_code=409, detail="card is not claimable")

            card.state = "CLAIMED"
            card.claimed_by = node_id
            card.lease_expires_at = self._now() + timedelta(seconds=lease_seconds)
            card.attempts += 1
            return card.model_copy(deep=True)

    def renew(self, card_id: str, node_id: str, lease_seconds: int) -> Card:
        if lease_seconds <= 0:
            raise HTTPException(status_code=400, detail="lease_seconds must be > 0")

        with self._lock:
            card = self._cards.get(card_id)
            if card is None:
                raise HTTPException(status_code=404, detail="card not found")

            self._normalize_for_expiry(card)
            if card.state != "CLAIMED" or card.claimed_by != node_id:
                raise HTTPException(status_code=403, detail="not current claimant")

            card.lease_expires_at = self._now() + timedelta(seconds=lease_seconds)
            return card.model_copy(deep=True)

    def complete(self, card_id: str, node_id: str, result: Any | None) -> Card:
        with self._lock:
            card = self._cards.get(card_id)
            if card is None:
                raise HTTPException(status_code=404, detail="card not found")

            self._normalize_for_expiry(card)
            if card.state == "DONE":
                if card.claimed_by == node_id:
                    return card.model_copy(deep=True)
                raise HTTPException(status_code=403, detail="already completed by another node")

            if card.state != "CLAIMED" or card.claimed_by != node_id:
                raise HTTPException(status_code=403, detail="not current claimant")

            card.state = "DONE"
            card.result = result
            card.lease_expires_at = None
            return card.model_copy(deep=True)

    def fail(self, card_id: str, node_id: str, result: Any | None) -> Card:
        with self._lock:
            card = self._cards.get(card_id)
            if card is None:
                raise HTTPException(status_code=404, detail="card not found")

            self._normalize_for_expiry(card)
            if card.state != "CLAIMED" or card.claimed_by != node_id:
                raise HTTPException(status_code=403, detail="not current claimant")

            card.state = "FAILED"
            card.result = result
            card.lease_expires_at = None
            return card.model_copy(deep=True)


store = InMemoryCardStore()


@app.get("/cards")
def get_cards(state: str = Query(default="open")) -> list[Card]:
    if state.lower() != "open":
        raise HTTPException(status_code=400, detail='only "open" filter is supported')
    return store.list_cards(state_filter="OPEN")


@app.post("/cards/{card_id}/claim")
def claim_card(card_id: str, request: ClaimRequest) -> Card:
    return store.claim(card_id=card_id, node_id=request.node_id, lease_seconds=request.lease_seconds)


@app.post("/cards/{card_id}/renew")
def renew_card(card_id: str, request: RenewRequest) -> Card:
    return store.renew(card_id=card_id, node_id=request.node_id, lease_seconds=request.lease_seconds)


@app.post("/cards/{card_id}/complete")
def complete_card(card_id: str, request: CompleteRequest) -> Card:
    return store.complete(card_id=card_id, node_id=request.node_id, result=request.result)


@app.post("/cards/{card_id}/fail")
def fail_card(card_id: str, request: FailRequest) -> Card:
    return store.fail(card_id=card_id, node_id=request.node_id, result=request.result)

