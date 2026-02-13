from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from orket.application.services.coordinator_store import InMemoryCoordinatorStore
from orket.core.domain.coordinator_card import Card


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
