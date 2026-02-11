from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from coordinator.models import Card


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    lease_duration: float


class RenewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    lease_duration: float


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    result: dict | None = None


class FailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    result: dict | None = None


class InMemoryCoordinatorStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cards: dict[str, Card] = {}
        self._lease_meta: dict[str, dict[str, Any]] = {}

    def reset(self, cards: list[Card]) -> None:
        with self._lock:
            self._cards = {card.id: card.model_copy(deep=True) for card in cards}
            self._lease_meta = {
                card.id: {
                    "lease_start": None,
                    "lease_duration": None,
                    "last_renew_at": None,
                    "primary_claimant": None,
                    "claimants": set(),
                    "winner": None,
                }
                for card in cards
            }

    def add_card(self, card: Card) -> None:
        with self._lock:
            self._cards[card.id] = card.model_copy(deep=True)
            self._lease_meta[card.id] = {
                "lease_start": None,
                "lease_duration": None,
                "last_renew_at": None,
                "primary_claimant": None,
                "claimants": set(),
                "winner": None,
            }

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def _get_meta(self, card_id: str) -> dict[str, Any]:
        meta = self._lease_meta.get(card_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="card not found")
        return meta

    def _get_card(self, card_id: str) -> Card:
        card = self._cards.get(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="card not found")
        return card

    def _is_expired(self, card: Card, now: float) -> bool:
        if card.lease_expires_at is None:
            return False
        return now >= card.lease_expires_at

    def _reopen_if_expired(self, card: Card, meta: dict[str, Any], now: float) -> None:
        if card.state == "CLAIMED" and self._is_expired(card, now):
            card.state = "OPEN"
            card.claimed_by = None
            card.lease_expires_at = None
            meta["lease_start"] = None
            meta["lease_duration"] = None
            meta["last_renew_at"] = None
            meta["primary_claimant"] = None
            meta["claimants"] = set()

    def list_open_cards(self) -> list[Card]:
        with self._lock:
            now = self._now()
            cards: list[Card] = []
            for card_id, card in self._cards.items():
                meta = self._get_meta(card_id)
                self._reopen_if_expired(card, meta, now)
                if card.state == "OPEN":
                    cards.append(card.model_copy(deep=True))
            return cards

    def _allow_hedged_claim(self, card: Card, meta: dict[str, Any], node_id: str, now: float) -> bool:
        if not card.hedged_execution:
            return False
        if node_id in meta["claimants"]:
            return True
        lease_start = meta["lease_start"]
        lease_duration = meta["lease_duration"]
        if lease_start is None or lease_duration is None:
            return False
        hedge_deadline = lease_start + (lease_duration / 2.0)
        if now < hedge_deadline:
            return False
        last_renew_at = meta["last_renew_at"]
        renewed_before_hedge = last_renew_at is not None and last_renew_at <= hedge_deadline
        return not renewed_before_hedge

    def claim(self, card_id: str, node_id: str, lease_duration: float) -> Card:
        if lease_duration <= 0:
            raise HTTPException(status_code=400, detail="lease_duration must be > 0")

        with self._lock:
            now = self._now()
            card = self._get_card(card_id)
            meta = self._get_meta(card_id)

            self._reopen_if_expired(card, meta, now)
            if card.state == "DONE" or card.state == "FAILED":
                raise HTTPException(status_code=409, detail="card is finalized")

            if card.state == "OPEN":
                card.state = "CLAIMED"
                card.claimed_by = node_id
                card.lease_expires_at = now + lease_duration
                card.attempts += 1
                meta["lease_start"] = now
                meta["lease_duration"] = lease_duration
                meta["last_renew_at"] = None
                meta["primary_claimant"] = node_id
                meta["claimants"] = {node_id}
                return card.model_copy(deep=True)

            if self._allow_hedged_claim(card, meta, node_id, now):
                meta["claimants"].add(node_id)
                card.attempts += 1
                card.lease_expires_at = now + lease_duration
                return card.model_copy(deep=True)

            raise HTTPException(status_code=409, detail="card is already claimed")

    def renew(self, card_id: str, node_id: str, lease_duration: float) -> Card:
        if lease_duration <= 0:
            raise HTTPException(status_code=400, detail="lease_duration must be > 0")

        with self._lock:
            now = self._now()
            card = self._get_card(card_id)
            meta = self._get_meta(card_id)

            self._reopen_if_expired(card, meta, now)
            if card.state != "CLAIMED":
                raise HTTPException(status_code=409, detail="card is not claimed")

            if card.hedged_execution:
                allowed = node_id in meta["claimants"]
            else:
                allowed = card.claimed_by == node_id

            if not allowed:
                raise HTTPException(status_code=403, detail="only claimant may renew")

            card.lease_expires_at = now + lease_duration
            meta["last_renew_at"] = now
            meta["lease_duration"] = lease_duration
            return card.model_copy(deep=True)

    def complete(self, card_id: str, node_id: str, result: dict | None) -> Card:
        with self._lock:
            now = self._now()
            card = self._get_card(card_id)
            meta = self._get_meta(card_id)
            self._reopen_if_expired(card, meta, now)

            if card.state == "DONE":
                return card.model_copy(deep=True)
            if card.state == "FAILED":
                raise HTTPException(status_code=409, detail="card already failed")
            if card.state != "CLAIMED":
                raise HTTPException(status_code=409, detail="card is not claimed")

            if card.hedged_execution:
                if node_id not in meta["claimants"]:
                    raise HTTPException(status_code=403, detail="only claimant may complete")
                if meta["winner"] is not None:
                    return card.model_copy(deep=True)
                meta["winner"] = node_id
            elif card.claimed_by != node_id:
                raise HTTPException(status_code=403, detail="only claimant may complete")

            card.state = "DONE"
            card.result = result
            card.claimed_by = None
            card.lease_expires_at = None
            meta["claimants"] = set()
            return card.model_copy(deep=True)

    def fail(self, card_id: str, node_id: str, result: dict | None) -> Card:
        with self._lock:
            now = self._now()
            card = self._get_card(card_id)
            meta = self._get_meta(card_id)
            self._reopen_if_expired(card, meta, now)

            if card.state == "DONE" or card.state == "FAILED":
                return card.model_copy(deep=True)
            if card.state != "CLAIMED":
                raise HTTPException(status_code=409, detail="card is not claimed")

            if card.hedged_execution:
                allowed = node_id in meta["claimants"]
            else:
                allowed = card.claimed_by == node_id
            if not allowed:
                raise HTTPException(status_code=403, detail="only claimant may fail")

            card.state = "FAILED"
            card.result = result
            card.claimed_by = None
            card.lease_expires_at = None
            meta["claimants"] = set()
            return card.model_copy(deep=True)


store = InMemoryCoordinatorStore()
store.reset(
    [
        Card(
            id="card-1",
            payload={"task": "demo"},
            state="OPEN",
            claimed_by=None,
            lease_expires_at=None,
            result=None,
            attempts=0,
            hedged_execution=False,
        )
    ]
)

app = FastAPI()


@app.get("/cards", response_model=list[Card])
def get_cards(state: str = Query(default="open")) -> list[Card]:
    if state.lower() != "open":
        raise HTTPException(status_code=400, detail='only "open" supported')
    return store.list_open_cards()


@app.post("/cards/{id}/claim", response_model=Card)
def claim_card(id: str, request: ClaimRequest) -> Card:
    return store.claim(id, request.node_id, request.lease_duration)


@app.post("/cards/{id}/renew", response_model=Card)
def renew_card(id: str, request: RenewRequest) -> Card:
    return store.renew(id, request.node_id, request.lease_duration)


@app.post("/cards/{id}/complete", response_model=Card)
def complete_card(id: str, request: CompleteRequest) -> Card:
    return store.complete(id, request.node_id, request.result)


@app.post("/cards/{id}/fail", response_model=Card)
def fail_card(id: str, request: FailRequest) -> Card:
    return store.fail(id, request.node_id, request.result)

