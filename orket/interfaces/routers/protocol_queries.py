"""Protocol inspection transport; application owns query policy and lifetime."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from orket.application.services.protocol_replay_service import LedgerFramingError, ProtocolReplayService


async def _query(operation: Awaitable[Any], *, framing_conflict: bool = False) -> Any:
    try:
        return await operation
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LedgerFramingError as exc:
        raise HTTPException(status_code=409 if framing_conflict else 400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def build_protocol_query_router(service_getter: Callable[[], ProtocolReplayService]) -> APIRouter:
    router = APIRouter()

    @router.get("/protocol/runs/{run_id}/replay")
    async def replay_protocol_run(run_id: str) -> Any:
        return await _query(service_getter().replay_protocol_run(run_id=run_id), framing_conflict=True)

    @router.get("/protocol/replay/compare")
    async def compare_protocol_replays(run_a: str, run_b: str) -> Any:
        return await _query(service_getter().compare_protocol_replays(run_a=run_a, run_b=run_b), framing_conflict=True)

    @router.get("/protocol/replay/campaign")
    async def campaign_protocol_replays(
        run_id: Annotated[list[str] | None, Query()] = None,
        baseline_run: str | None = None, runs_root: str | None = None,
    ) -> Any:
        return await _query(service_getter().compare_protocol_determinism_campaign(
            run_ids=list(run_id or []), baseline_run=baseline_run, runs_root=runs_root,
        ))

    @router.get("/protocol/runs/{run_id}/ledger-parity")
    async def compare_protocol_and_sqlite_run_ledgers(run_id: str, sqlite_db_path: str | None = None) -> Any:
        return await _query(service_getter().compare_protocol_and_sqlite_run_ledgers(
            run_id=run_id, sqlite_db_path=sqlite_db_path,
        ), framing_conflict=True)

    @router.get("/protocol/ledger-parity/campaign")
    async def campaign_protocol_ledger_parity(
        session_id: Annotated[list[str] | None, Query()] = None,
        sqlite_db_path: str | None = None, discover_limit: int = 200,
    ) -> Any:
        return await _query(service_getter().compare_protocol_ledger_parity_campaign(
            session_ids=list(session_id or []), sqlite_db_path=sqlite_db_path, discover_limit=discover_limit,
        ))

    return router
