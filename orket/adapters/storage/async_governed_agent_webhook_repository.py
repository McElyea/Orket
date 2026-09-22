from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
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
from orket.core.contracts.governed_agent_webhook_records import (
    GovernedAgentWebhookDeliveryRecord,
    GovernedAgentWebhookDeliveryRequest,
    GovernedAgentWebhookDeliveryResult,
    WebhookDeliveryStatus,
)

ResultT = TypeVar("ResultT")


side_effecting = True


class AsyncGovernedAgentWebhookRepository:
    """Atomically retain authenticated webhook deliveries and their wake."""

    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def apply_delivery(
        self,
        request: GovernedAgentWebhookDeliveryRequest,
    ) -> GovernedAgentWebhookDeliveryResult:
        normalized = _validated_request(request)
        serialized = payload_json(normalized.request)
        digest = payload_digest(serialized)

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentWebhookDeliveryResult:
            await conn.execute("BEGIN IMMEDIATE")
            retained = await _delivery_row(conn, normalized.delivery_ref)
            if retained is not None:
                record = _delivery_record(retained)
                wake = None if record.resulting_wake_id is None else await get_wake(conn, record.resulting_wake_id)
                status: WebhookDeliveryStatus = "idempotent" if record.request_digest == digest else "conflict"
                return GovernedAgentWebhookDeliveryResult(status, record, wake)
            wake_result = await enqueue_transaction(
                conn,
                normalized.selected_wake,
                begin=False,
                admit_webhook=True,
            )
            status = cast(WebhookDeliveryStatus, wake_result.status)
            resulting_wake_id = (
                None if status == "conflict" or wake_result.wake is None else wake_result.wake.wake_id
            )
            await _insert_delivery(
                conn,
                request=normalized,
                serialized=serialized,
                digest=digest,
                status=status,
                resulting_wake_id=resulting_wake_id,
            )
            row = await _delivery_row(conn, normalized.delivery_ref)
            if row is None:
                raise RuntimeError("E_AGENT_WEBHOOK_DELIVERY_PUBLICATION_MISSING")
            return GovernedAgentWebhookDeliveryResult(status, _delivery_record(row), wake_result.wake)

        return await self._execute(_op)

    async def list_deliveries(
        self,
        *,
        issuer_ref: str,
    ) -> tuple[GovernedAgentWebhookDeliveryRecord, ...]:
        issuer = required_text(issuer_ref, "E_AGENT_WEBHOOK_ISSUER_REQUIRED")

        async def _op(conn: aiosqlite.Connection) -> tuple[GovernedAgentWebhookDeliveryRecord, ...]:
            cursor = await conn.execute(
                """
                SELECT * FROM governed_agent_webhook_deliveries
                WHERE issuer_ref = ? ORDER BY received_at_utc, delivery_ref
                """,
                (issuer,),
            )
            return tuple(_delivery_record(row) for row in await cursor.fetchall())

        return await self._execute(_op)

    async def get_delivery(
        self,
        *,
        delivery_ref: str,
    ) -> GovernedAgentWebhookDeliveryRecord | None:
        normalized_ref = required_text(delivery_ref, "E_AGENT_WEBHOOK_DELIVERY_REF_REQUIRED")

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentWebhookDeliveryRecord | None:
            row = await _delivery_row(conn, normalized_ref)
            return None if row is None else _delivery_record(row)

        return await self._execute(_op)

    async def _execute(self, operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]]) -> ResultT:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await ensure_schema(conn)
                await _ensure_webhook_schema(conn)
                self._initialized = True
            result = await operation(conn)
            await conn.commit()
            return result


async def _ensure_webhook_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS governed_agent_webhook_deliveries (
            delivery_ref TEXT PRIMARY KEY, issuer_ref TEXT NOT NULL,
            delivery_id TEXT NOT NULL, key_id TEXT NOT NULL,
            delivered_at_utc TEXT NOT NULL, received_at_utc TEXT NOT NULL,
            request_json TEXT NOT NULL, request_digest TEXT NOT NULL,
            content_digest TEXT NOT NULL, status TEXT NOT NULL,
            resulting_wake_id TEXT,
            UNIQUE (issuer_ref, delivery_id)
        );
        CREATE INDEX IF NOT EXISTS idx_governed_agent_webhook_deliveries_issuer
        ON governed_agent_webhook_deliveries(issuer_ref, received_at_utc, delivery_ref);
        """
    )


async def _insert_delivery(
    conn: aiosqlite.Connection,
    *,
    request: GovernedAgentWebhookDeliveryRequest,
    serialized: str,
    digest: str,
    status: WebhookDeliveryStatus,
    resulting_wake_id: str | None,
) -> None:
    await conn.execute(
        """
        INSERT INTO governed_agent_webhook_deliveries (
            delivery_ref, issuer_ref, delivery_id, key_id, delivered_at_utc,
            received_at_utc, request_json, request_digest, content_digest,
            status, resulting_wake_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.delivery_ref,
            request.issuer_ref,
            request.delivery_id,
            request.key_id,
            request.delivered_at_utc,
            request.received_at_utc,
            serialized,
            digest,
            str(request.request["content_digest"]),
            status,
            resulting_wake_id,
        ),
    )


def _validated_request(
    request: GovernedAgentWebhookDeliveryRequest,
) -> GovernedAgentWebhookDeliveryRequest:
    if not isinstance(request.request, Mapping):
        raise ValueError("E_AGENT_WEBHOOK_DELIVERY_PAYLOAD_REQUIRED")
    normalized = GovernedAgentWebhookDeliveryRequest(
        delivery_ref=required_text(request.delivery_ref, "E_AGENT_WEBHOOK_DELIVERY_REF_REQUIRED"),
        issuer_ref=required_text(request.issuer_ref, "E_AGENT_WEBHOOK_ISSUER_REQUIRED"),
        delivery_id=required_text(request.delivery_id, "E_AGENT_WEBHOOK_DELIVERY_ID_REQUIRED"),
        key_id=required_text(request.key_id, "E_AGENT_WEBHOOK_KEY_ID_REQUIRED"),
        delivered_at_utc=utc_timestamp(request.delivered_at_utc),
        received_at_utc=utc_timestamp(request.received_at_utc),
        request=dict(request.request),
        selected_wake=request.selected_wake,
    )
    _validate_request_linkage(normalized)
    return normalized


def _validate_request_linkage(request: GovernedAgentWebhookDeliveryRequest) -> None:
    payload = request.request
    wake = request.selected_wake
    trigger = wake.payload.get("trigger")
    if (
        payload.get("schema_version") != "governed_agent_webhook_delivery.v1"
        or payload.get("delivery_ref") != request.delivery_ref
        or payload.get("issuer_ref") != request.issuer_ref
        or payload.get("delivery_id") != request.delivery_id
        or payload.get("key_id") != request.key_id
        or payload.get("delivered_at_utc") != request.delivered_at_utc
        or not isinstance(payload.get("content_digest"), str)
        or wake.source != "webhook"
        or wake.occurrence_id != request.delivery_ref
        or not isinstance(trigger, Mapping)
        or trigger.get("delivery_ref") != request.delivery_ref
        or trigger.get("received_at_utc") != request.received_at_utc
    ):
        raise ValueError("E_AGENT_WEBHOOK_DELIVERY_LINKAGE_INVALID")


async def _delivery_row(conn: aiosqlite.Connection, delivery_ref: str) -> aiosqlite.Row | None:
    cursor = await conn.execute(
        "SELECT * FROM governed_agent_webhook_deliveries WHERE delivery_ref = ?",
        (delivery_ref,),
    )
    return await cursor.fetchone()


def _delivery_record(row: aiosqlite.Row) -> GovernedAgentWebhookDeliveryRecord:
    return GovernedAgentWebhookDeliveryRecord(
        delivery_ref=str(row["delivery_ref"]),
        issuer_ref=str(row["issuer_ref"]),
        delivery_id=str(row["delivery_id"]),
        key_id=str(row["key_id"]),
        delivered_at_utc=str(row["delivered_at_utc"]),
        received_at_utc=str(row["received_at_utc"]),
        request=dict(json.loads(str(row["request_json"]))),
        request_digest=str(row["request_digest"]),
        content_digest=str(row["content_digest"]),
        status=cast(WebhookDeliveryStatus, str(row["status"])),
        resulting_wake_id=_optional_text(row["resulting_wake_id"]),
    )


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
