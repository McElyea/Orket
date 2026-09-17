from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from orket.application.services.outward_ledger_service import OutwardLedgerValidationError


class LedgerVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_anchor: dict[str, Any]


def build_outward_ledger_router(
    *, service_getter: Callable[[], Any], outbound_filter: Callable[[Any, str], Any],
) -> APIRouter:
    router = APIRouter()

    async def verify(run_id: str, external_anchor: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            payload = await service_getter().verify_run(run_id, external_anchor=external_anchor)
        except OutwardLedgerValidationError as exc:
            raise _http_error(exc) from exc
        return outbound_filter(payload, "api.runs.ledger.verify")

    @router.get("/runs/{run_id}/ledger")
    async def export_ledger(
        run_id: str, request: Request, types: str | None = Query(default=None),
        include_pii: bool = Query(default=False),
    ) -> dict[str, Any]:
        try:
            payload = await service_getter().export(
                run_id, types=tuple(item.strip() for item in (types or "").split(",") if item.strip()),
                include_pii=include_pii, record_request=include_pii,
                operator_ref=getattr(request.state, "authenticated_actor_ref", None) or "operator:unknown",
            )
        except OutwardLedgerValidationError as exc:
            raise _http_error(exc) from exc
        return outbound_filter(payload, "api.runs.ledger")

    @router.get("/runs/{run_id}/ledger/verify")
    async def verify_ledger(run_id: str) -> dict[str, Any]:
        return await verify(run_id)

    @router.post("/runs/{run_id}/ledger/verify")
    async def verify_with_anchor(run_id: str, body: LedgerVerifyRequest) -> dict[str, Any]:
        return await verify(run_id, body.external_anchor)

    return router


def _http_error(exc: OutwardLedgerValidationError) -> HTTPException:
    return HTTPException(status_code=404 if "not found" in str(exc).lower() else 422, detail=str(exc))
