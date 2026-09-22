from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import TypeVar, cast

import aiosqlite

from orket.adapters.storage.governed_agent_wake_repository_support import (
    enqueue_transaction,
    ensure_schema,
    get_wake,
    payload_digest,
    payload_json,
    required_text,
    utc_timestamp,
)
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.core.contracts.governed_agent_schedule_records import (
    GovernedAgentScheduleEvaluationRecord,
    GovernedAgentScheduleEvaluationRequest,
    GovernedAgentScheduleEvaluationResult,
    ScheduleEvaluationStatus,
)

ResultT = TypeVar("ResultT")


side_effecting = True


class AsyncGovernedAgentScheduleRepository:
    """Atomically retain schedule evaluations and their selected wake."""

    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def apply_evaluation(
        self,
        request: GovernedAgentScheduleEvaluationRequest,
    ) -> GovernedAgentScheduleEvaluationResult:
        normalized = _validated_request(request)
        serialized = payload_json(normalized.request)
        digest = payload_digest(serialized)

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentScheduleEvaluationResult:
            await conn.execute("BEGIN IMMEDIATE")
            retained = await _evaluation_row(conn, normalized.evaluation_id)
            if retained is not None:
                record = _evaluation_record(retained)
                wake = None if record.resulting_wake_id is None else await get_wake(conn, record.resulting_wake_id)
                status: ScheduleEvaluationStatus = "idempotent" if record.request_digest == digest else "conflict"
                return GovernedAgentScheduleEvaluationResult(status, record, wake)
            wake_result = (
                None
                if normalized.selected_wake is None
                else await enqueue_transaction(
                    conn,
                    normalized.selected_wake,
                    begin=False,
                    admit_scheduled=True,
                )
            )
            status = "skipped" if wake_result is None else wake_result.status
            resulting_wake_id = (
                None
                if wake_result is None or wake_result.status == "conflict" or wake_result.wake is None
                else wake_result.wake.wake_id
            )
            await _insert_evaluation(
                conn,
                request=normalized,
                serialized=serialized,
                digest=digest,
                status=cast(ScheduleEvaluationStatus, status),
                resulting_wake_id=resulting_wake_id,
            )
            row = await _evaluation_row(conn, normalized.evaluation_id)
            if row is None:
                raise RuntimeError("E_AGENT_SCHEDULE_EVALUATION_PUBLICATION_MISSING")
            return GovernedAgentScheduleEvaluationResult(
                cast(ScheduleEvaluationStatus, status),
                _evaluation_record(row),
                None if wake_result is None else wake_result.wake,
            )

        return await self._execute(_op)

    async def list_evaluations(
        self,
        *,
        schedule_id: str,
    ) -> tuple[GovernedAgentScheduleEvaluationRecord, ...]:
        normalized_id = required_text(schedule_id, "E_AGENT_SCHEDULE_ID_REQUIRED")

        async def _op(conn: aiosqlite.Connection) -> tuple[GovernedAgentScheduleEvaluationRecord, ...]:
            cursor = await conn.execute(
                """
                SELECT * FROM governed_agent_schedule_evaluations
                WHERE schedule_id = ? ORDER BY evaluated_at_utc, evaluation_id
                """,
                (normalized_id,),
            )
            return tuple(_evaluation_record(row) for row in await cursor.fetchall())

        return await self._execute(_op)

    async def get_evaluation(
        self,
        *,
        evaluation_id: str,
    ) -> GovernedAgentScheduleEvaluationRecord | None:
        normalized_id = required_text(evaluation_id, "E_AGENT_SCHEDULE_EVALUATION_ID_REQUIRED")

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentScheduleEvaluationRecord | None:
            row = await _evaluation_row(conn, normalized_id)
            return None if row is None else _evaluation_record(row)

        return await self._execute(_op)

    async def _execute(self, operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]]) -> ResultT:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await ensure_schema(conn)
                await _ensure_schedule_schema(conn)
                self._initialized = True
            result = await operation(conn)
            await conn.commit()
            return result


async def _ensure_schedule_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS governed_agent_schedule_evaluations (
            evaluation_id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL,
            evaluated_at_utc TEXT NOT NULL, request_json TEXT NOT NULL,
            request_digest TEXT NOT NULL, status TEXT NOT NULL,
            selected_occurrence_id TEXT, coalesced_occurrence_ids_json TEXT NOT NULL,
            skipped_occurrence_ids_json TEXT NOT NULL, resulting_wake_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_governed_agent_schedule_evaluations_schedule
        ON governed_agent_schedule_evaluations(schedule_id, evaluated_at_utc, evaluation_id);
        """
    )


async def _insert_evaluation(
    conn: aiosqlite.Connection,
    *,
    request: GovernedAgentScheduleEvaluationRequest,
    serialized: str,
    digest: str,
    status: ScheduleEvaluationStatus,
    resulting_wake_id: str | None,
) -> None:
    payload = request.request
    await conn.execute(
        """
        INSERT INTO governed_agent_schedule_evaluations (
            evaluation_id, schedule_id, evaluated_at_utc, request_json,
            request_digest, status, selected_occurrence_id,
            coalesced_occurrence_ids_json, skipped_occurrence_ids_json,
            resulting_wake_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.evaluation_id,
            request.schedule_id,
            request.evaluated_at_utc,
            serialized,
            digest,
            status,
            _optional_text(payload.get("selected_occurrence_id")),
            json.dumps(list(_text_items(payload.get("coalesced_occurrence_ids")))),
            json.dumps(list(_text_items(payload.get("skipped_occurrence_ids")))),
            resulting_wake_id,
        ),
    )


def _validated_request(
    request: GovernedAgentScheduleEvaluationRequest,
) -> GovernedAgentScheduleEvaluationRequest:
    if not isinstance(request.request, Mapping):
        raise ValueError("E_AGENT_SCHEDULE_EVALUATION_PAYLOAD_REQUIRED")
    normalized = GovernedAgentScheduleEvaluationRequest(
        evaluation_id=required_text(request.evaluation_id, "E_AGENT_SCHEDULE_EVALUATION_ID_REQUIRED"),
        schedule_id=required_text(request.schedule_id, "E_AGENT_SCHEDULE_ID_REQUIRED"),
        evaluated_at_utc=utc_timestamp(request.evaluated_at_utc),
        request=dict(request.request),
        selected_wake=request.selected_wake,
    )
    _validate_request_linkage(normalized)
    return normalized


def _validate_request_linkage(request: GovernedAgentScheduleEvaluationRequest) -> None:
    payload = request.request
    if (
        payload.get("schema_version") != "governed_agent_schedule_evaluation.v1"
        or payload.get("evaluation_id") != request.evaluation_id
        or payload.get("schedule_id") != request.schedule_id
        or payload.get("observed_at_utc") != request.evaluated_at_utc
    ):
        raise ValueError("E_AGENT_SCHEDULE_EVALUATION_LINKAGE_INVALID")
    selected_id = _optional_text(payload.get("selected_occurrence_id"))
    if selected_id is None and request.selected_wake is not None:
        raise ValueError("E_AGENT_SCHEDULE_EVALUATION_LINKAGE_INVALID")
    if selected_id is not None:
        wake = request.selected_wake
        trigger = None if wake is None else wake.payload.get("trigger")
        if (
            wake is None
            or wake.source != "scheduled"
            or wake.occurrence_id != selected_id
            or not isinstance(trigger, Mapping)
            or trigger.get("evaluation_id") != request.evaluation_id
            or trigger.get("schedule_id") != request.schedule_id
        ):
            raise ValueError("E_AGENT_SCHEDULE_EVALUATION_LINKAGE_INVALID")


async def _evaluation_row(conn: aiosqlite.Connection, evaluation_id: str) -> aiosqlite.Row | None:
    cursor = await conn.execute(
        "SELECT * FROM governed_agent_schedule_evaluations WHERE evaluation_id = ?",
        (evaluation_id,),
    )
    return await cursor.fetchone()


def _evaluation_record(row: aiosqlite.Row) -> GovernedAgentScheduleEvaluationRecord:
    return GovernedAgentScheduleEvaluationRecord(
        evaluation_id=str(row["evaluation_id"]),
        schedule_id=str(row["schedule_id"]),
        evaluated_at_utc=str(row["evaluated_at_utc"]),
        request=dict(json.loads(str(row["request_json"]))),
        request_digest=str(row["request_digest"]),
        status=cast(ScheduleEvaluationStatus, str(row["status"])),
        selected_occurrence_id=_optional_text(row["selected_occurrence_id"]),
        coalesced_occurrence_ids=tuple(json.loads(str(row["coalesced_occurrence_ids_json"]))),
        skipped_occurrence_ids=tuple(json.loads(str(row["skipped_occurrence_ids_json"]))),
        resulting_wake_id=_optional_text(row["resulting_wake_id"]),
    )


def _text_items(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value)


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
