from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orket.application.services.card_authoring_runtime_projection_service import (
    CardAuthoringRuntimeProjectionService,
)
from orket.application.services.card_authoring_service import (
    CardAuthoringConflictError,
    CardAuthoringNotFoundError,
    CardAuthoringService,
    CardDraftWriteModel,
)


class CardCreateRequest(BaseModel):
    draft: CardDraftWriteModel


class CardUpdateRequest(BaseModel):
    draft: CardDraftWriteModel
    expected_revision_id: str | None = None


class CardValidationRequest(BaseModel):
    draft: CardDraftWriteModel


def build_card_authoring_router(
    engine_getter: Callable[[], Any],
    project_root_getter: Callable[[], Any],
) -> APIRouter:
    router = APIRouter()

    def _service() -> CardAuthoringService:
        engine = engine_getter()
        return CardAuthoringService(
            cards_repo=engine.cards,
            now_iso_factory=lambda: datetime.now(UTC).isoformat(),
            card_id_factory=lambda: f"CARD-{uuid4().hex[:8].upper()}",
            revision_id_factory=lambda: f"crv_{uuid4().hex}",
            runtime_projection_service=CardAuthoringRuntimeProjectionService(project_root=project_root_getter()),
        )

    @router.post("/cards")
    async def create_card(req: CardCreateRequest) -> dict[str, Any]:
        result = await _service().create_card(req.draft)
        return result.model_dump()

    @router.put("/cards/{card_id}")
    async def save_card(card_id: str, req: CardUpdateRequest) -> dict[str, Any]:
        try:
            result = await _service().update_card(
                card_id=card_id,
                draft=req.draft,
                expected_revision_id=req.expected_revision_id,
            )
        except CardAuthoringNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Card '{exc}' not found") from exc
        except CardAuthoringConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return result.model_dump()

    @router.post("/cards/validate")
    async def validate_card(req: CardValidationRequest) -> dict[str, Any]:
        result = _service().validate_draft(req.draft)
        return result.model_dump()

    return router
