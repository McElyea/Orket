"""Standalone coordinator transport; applications and authority are explicitly owned."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.coordinator_read_service import CoordinatorCardResponse
from orket.application.services.coordinator_runtime_service import (
    CoordinatorRuntimeService,
    CoordinatorUnavailableError,
)
from orket.application.services.coordinator_store import (
    CoordinatorConflictError,
    CoordinatorNotFoundError,
    CoordinatorPermissionError,
    CoordinatorStoreError,
    CoordinatorValidationError,
    InMemoryCoordinatorStore,
)
from orket.application.services.runtime_input_service import RuntimeInputService


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    lease_duration: float


class RenewRequest(ClaimRequest):
    """Renewal uses the same node/duration contract as claim."""


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    result: dict[str, Any] | None = None


class FailRequest(CompleteRequest):
    """Failure uses the same node/result contract as completion."""


@asynccontextmanager
async def _lifespan(app: FastAPI):
    try:
        yield
    finally:
        await app.state.coordinator.close()


def create_coordinator_app(
    *, project_root: Path | None = None, environment: Mapping[str, str] | None = None,
    runtime_inputs: RuntimeInputService | None = None, store: InMemoryCoordinatorStore | None = None,
    publication: ControlPlanePublicationService | None = None,
) -> FastAPI:
    app = FastAPI(lifespan=_lifespan)
    app.state.coordinator = CoordinatorRuntimeService(
        project_root=project_root, environment=environment, runtime_inputs=runtime_inputs,
        store=store, publication=publication,
    )
    app.add_api_route("/cards", get_cards, methods=["GET"], response_model=list[CoordinatorCardResponse])
    for suffix, endpoint in (("claim", claim_card), ("renew", renew_card), ("complete", complete_card), ("fail", fail_card)):
        app.add_api_route("/cards/{id}/" + suffix, endpoint, methods=["POST"], response_model=CoordinatorCardResponse)
    return app


async def _perform(request: Request, operation: str, **values):
    try:
        return await request.app.state.coordinator.execute(operation, **values)
    except CoordinatorUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CoordinatorStoreError as exc:
        for error_type, status in ((CoordinatorValidationError, 400), (CoordinatorNotFoundError, 404),
                                   (CoordinatorPermissionError, 403), (CoordinatorConflictError, 409)):
            if isinstance(exc, error_type):
                raise HTTPException(status_code=status, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail="unexpected coordinator store error") from exc


async def get_cards(request: Request, state: str = Query(default="open")) -> list[CoordinatorCardResponse]:
    if state.lower() != "open":
        raise HTTPException(status_code=400, detail='only "open" supported')
    return await _perform(request, "list")


async def claim_card(id: str, payload: ClaimRequest, request: Request) -> CoordinatorCardResponse:
    return await _perform(request, "claim", card_id=id, node_id=payload.node_id, lease_duration=payload.lease_duration)


async def renew_card(id: str, payload: RenewRequest, request: Request) -> CoordinatorCardResponse:
    return await _perform(request, "renew", card_id=id, node_id=payload.node_id, lease_duration=payload.lease_duration)


async def complete_card(id: str, payload: CompleteRequest, request: Request) -> CoordinatorCardResponse:
    return await _perform(request, "complete", card_id=id, node_id=payload.node_id, result=payload.result)


async def fail_card(id: str, payload: FailRequest, request: Request) -> CoordinatorCardResponse:
    return await _perform(request, "fail", card_id=id, node_id=payload.node_id, result=payload.result)
