from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any, Literal, TypeVar

import aiosqlite

from orket.adapters.storage.governed_agent_decision_store import GovernedAgentDecisionStore
from orket.adapters.storage.governed_agent_repository_support import (
    agent_digest,
    binding_from_json,
    binding_json,
    budget_admits,
    call_record,
    call_ref,
    call_row,
    dispatch_ref,
    ensure_governed_agent_schema,
    existing_acceptance,
    host_model_receipts_match,
    invocation_row,
    optional_json,
    optional_payload,
    parent_matches,
    require_call_row,
    result_ref,
)
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.core.contracts.governed_agent_ports import (
    GovernedAgentBrokerCallRecord,
    GovernedAgentBrokerReservation,
    GovernedAgentCancellationPublication,
    GovernedAgentDecisionPublication,
    GovernedAgentDispatchPreparation,
    GovernedAgentInvocationBinding,
    GovernedAgentInvocationOutcome,
    GovernedAgentIterationSnapshot,
    GovernedAgentResultAcceptance,
)
from orket_extension_sdk import (
    AgentIterationRequest,
    validate_agent_iteration_result_against_request,
)

ResultT = TypeVar("ResultT")


class AsyncGovernedAgentRepository:
    """Atomic SQLite authority for agent dispatch, results, and broker calls."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False
        self._decisions = GovernedAgentDecisionStore(self._execute)

    async def prepare_dispatch(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        request_payload: Mapping[str, Any],
    ) -> GovernedAgentDispatchPreparation:
        request = AgentIterationRequest.from_wire(dict(request_payload))
        request_json = json.dumps(request.to_wire(), sort_keys=True, separators=(",", ":"))
        if binding.request_digest != agent_digest(json.loads(request_json)):
            return GovernedAgentDispatchPreparation("conflict", None, None)

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentDispatchPreparation:
            await conn.execute("BEGIN IMMEDIATE")
            if not await parent_matches(conn, binding):
                return GovernedAgentDispatchPreparation("stale", None, None)
            row = await invocation_row(conn, binding.invocation_id)
            if row is not None:
                existing = binding_from_json(str(row["binding_json"]))
                if existing == binding and str(row["request_json"]) == request_json:
                    return GovernedAgentDispatchPreparation(
                        "idempotent",
                        existing,
                        dispatch_ref(binding.invocation_id),
                    )
                return GovernedAgentDispatchPreparation("conflict", None, None)
            await conn.execute(
                """
                INSERT INTO governed_agent_invocations
                    (invocation_id, binding_json, request_json, state, uncertainty)
                VALUES (?, ?, ?, 'prepared', 0)
                """,
                (binding.invocation_id, binding_json(binding), request_json),
            )
            return GovernedAgentDispatchPreparation("prepared", binding, dispatch_ref(binding.invocation_id))

        return await self._execute(_op)

    async def get_dispatch_binding(
        self,
        *,
        invocation_id: str,
    ) -> GovernedAgentInvocationBinding | None:
        return await self._decisions.get_binding(invocation_id=invocation_id)

    async def get_dispatch_request(
        self,
        *,
        invocation_id: str,
    ) -> Mapping[str, Any] | None:
        return await self._decisions.get_request(invocation_id=invocation_id)

    async def accept_result(
        self,
        *,
        outcome: GovernedAgentInvocationOutcome,
    ) -> GovernedAgentResultAcceptance:
        if outcome.status == "returned" and (
            outcome.result_payload is None
            or outcome.result_digest != agent_digest(dict(outcome.result_payload))
        ):
            return GovernedAgentResultAcceptance("conflict", None, None)

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentResultAcceptance:
            await conn.execute("BEGIN IMMEDIATE")
            row = await invocation_row(conn, outcome.binding.invocation_id)
            if row is None:
                return GovernedAgentResultAcceptance("stale", None, None)
            if binding_from_json(str(row["binding_json"])) != outcome.binding:
                return GovernedAgentResultAcceptance("stale", None, None)
            if not await parent_matches(conn, outcome.binding):
                return GovernedAgentResultAcceptance("stale", None, None)
            if str(row["state"]) != "prepared":
                return existing_acceptance(row, outcome)
            if outcome.status == "returned":
                if outcome.result_payload is None:
                    return GovernedAgentResultAcceptance("conflict", None, None)
                request = json.loads(str(row["request_json"]))
                validate_agent_iteration_result_against_request(request=request, result=outcome.result_payload)
                if not await host_model_receipts_match(
                    conn,
                    outcome.binding.invocation_id,
                    dict(outcome.result_payload),
                ):
                    return GovernedAgentResultAcceptance("conflict", None, None)
            result_json = optional_json(dict(outcome.result_payload) if outcome.result_payload is not None else None)
            await conn.execute(
                """
                UPDATE governed_agent_invocations
                SET state = ?, result_json = ?, result_digest = ?, normalized_reason = ?
                WHERE invocation_id = ?
                """,
                (
                    "returned" if outcome.status == "returned" else outcome.status,
                    result_json,
                    outcome.result_digest,
                    outcome.normalized_reason,
                    outcome.binding.invocation_id,
                ),
            )
            return GovernedAgentResultAcceptance(
                "accepted",
                result_ref(outcome.binding.invocation_id),
                outcome.result_digest,
            )

        return await self._execute(_op)

    async def record_interrupted_publication(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        normalized_reason: str,
        provider_or_effect_uncertain: bool,
    ) -> str:
        return await self._decisions.record_interrupted(
            binding=binding,
            normalized_reason=normalized_reason,
            provider_or_effect_uncertain=provider_or_effect_uncertain,
        )

    async def publish_continuation_decision(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        accepted_result_digest: str,
        decision_inputs: Mapping[str, Any],
        decision_payload: Mapping[str, Any],
    ) -> GovernedAgentDecisionPublication:
        return await self._decisions.publish(
            binding=binding,
            accepted_result_digest=accepted_result_digest,
            decision_inputs=decision_inputs,
            decision_payload=decision_payload,
        )

    async def get_iteration_snapshot(
        self,
        *,
        invocation_id: str,
    ) -> GovernedAgentIterationSnapshot | None:
        return await self._decisions.get_snapshot(invocation_id=invocation_id)

    async def list_iteration_snapshots(
        self,
        *,
        run_id: str,
    ) -> tuple[GovernedAgentIterationSnapshot, ...]:
        return await self._decisions.list_snapshots(run_id=run_id)

    async def cancel_invocation(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        cancellation_epoch: int,
        normalized_reason: str,
    ) -> GovernedAgentCancellationPublication:
        return await self._decisions.cancel(
            binding=binding,
            cancellation_epoch=cancellation_epoch,
            normalized_reason=normalized_reason,
        )

    async def reserve_call(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        operation: Literal["model.call.v1", "memory.query.v1"],
        call_id: str,
        role: str | None,
        request_digest: str,
        reserved_input_tokens: int,
        reserved_output_tokens: int,
    ) -> GovernedAgentBrokerReservation:
        async def _op(conn: aiosqlite.Connection) -> GovernedAgentBrokerReservation:
            await conn.execute("BEGIN IMMEDIATE")
            invocation = await invocation_row(conn, binding.invocation_id)
            if invocation is None or binding_from_json(str(invocation["binding_json"])) != binding:
                return GovernedAgentBrokerReservation("stale", None, None)
            if not await parent_matches(conn, binding):
                return GovernedAgentBrokerReservation("stale", None, None)
            if str(invocation["state"]) != "prepared":
                return GovernedAgentBrokerReservation("cancelled", None, None)
            existing = await call_row(conn, binding.invocation_id, call_id)
            if existing is not None:
                if str(existing["request_digest"]) != request_digest or str(existing["operation"]) != operation:
                    return GovernedAgentBrokerReservation("conflict", None, None)
                if str(existing["status"]) != "completed":
                    return GovernedAgentBrokerReservation(
                        "uncertain",
                        call_ref(binding.invocation_id, call_id),
                        None,
                    )
                return GovernedAgentBrokerReservation(
                    "idempotent",
                    call_ref(binding.invocation_id, call_id),
                    optional_payload(existing["result_json"]),
                )
            request = json.loads(str(invocation["request_json"]))
            if not await budget_admits(
                conn,
                binding.invocation_id,
                request,
                operation=operation,
                role=role,
                input_tokens=reserved_input_tokens,
                output_tokens=reserved_output_tokens,
            ):
                return GovernedAgentBrokerReservation("exhausted", None, None)
            await conn.execute(
                """
                INSERT INTO governed_agent_calls
                    (invocation_id, call_id, operation, role, request_digest, status,
                     reserved_input_tokens, reserved_output_tokens, charged_input_tokens,
                     charged_output_tokens)
                VALUES (?, ?, ?, ?, ?, 'reserved', ?, ?, 0, 0)
                """,
                (
                    binding.invocation_id,
                    call_id,
                    operation,
                    role,
                    request_digest,
                    reserved_input_tokens,
                    reserved_output_tokens,
                ),
            )
            return GovernedAgentBrokerReservation("prepared", call_ref(binding.invocation_id, call_id), None)

        return await self._execute(_op)

    async def complete_call(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        call_id: str,
        request_digest: str,
        result_payload: Mapping[str, Any],
        result_digest: str,
        charged_input_tokens: int,
        charged_output_tokens: int,
    ) -> GovernedAgentBrokerCallRecord:
        if result_digest != agent_digest(dict(result_payload)):
            raise ValueError("E_AGENT_BROKER_RESULT_DIGEST_MISMATCH")

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentBrokerCallRecord:
            await conn.execute("BEGIN IMMEDIATE")
            row = await require_call_row(conn, binding, call_id)
            invocation = await invocation_row(conn, binding.invocation_id)
            if invocation is None or str(invocation["state"]) != "prepared":
                raise ValueError("E_AGENT_BROKER_INVOCATION_INACTIVE")
            if not await parent_matches(conn, binding):
                raise ValueError("E_AGENT_BROKER_BINDING_STALE")
            if str(row["request_digest"]) != request_digest:
                raise ValueError("E_AGENT_BROKER_REQUEST_DIGEST_MISMATCH")
            if charged_input_tokens > int(row["reserved_input_tokens"]) or charged_output_tokens > int(
                row["reserved_output_tokens"]
            ):
                raise ValueError("E_AGENT_BROKER_CHARGE_EXCEEDS_RESERVATION")
            result_json = json.dumps(dict(result_payload), sort_keys=True, separators=(",", ":"))
            if str(row["status"]) == "completed":
                result_conflicts = (
                    str(row["result_digest"]) != result_digest
                    or int(row["charged_input_tokens"]) != charged_input_tokens
                    or int(row["charged_output_tokens"]) != charged_output_tokens
                )
                if result_conflicts:
                    raise ValueError("E_AGENT_BROKER_RESULT_CONFLICT")
                return call_record(row)
            if str(row["status"]) == "uncertain":
                raise ValueError("E_AGENT_BROKER_CALL_UNCERTAIN")
            await conn.execute(
                """
                UPDATE governed_agent_calls
                SET status = 'completed', charged_input_tokens = ?, charged_output_tokens = ?,
                    result_digest = ?, result_json = ?
                WHERE invocation_id = ? AND call_id = ?
                """,
                (
                    charged_input_tokens,
                    charged_output_tokens,
                    result_digest,
                    result_json,
                    binding.invocation_id,
                    call_id,
                ),
            )
            updated = await call_row(conn, binding.invocation_id, call_id)
            if updated is None:
                raise ValueError("E_AGENT_BROKER_CALL_MISSING")
            return call_record(updated)

        return await self._execute(_op)

    async def mark_call_uncertain(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        call_id: str,
        normalized_reason: str,
    ) -> GovernedAgentBrokerCallRecord:
        async def _op(conn: aiosqlite.Connection) -> GovernedAgentBrokerCallRecord:
            await conn.execute("BEGIN IMMEDIATE")
            row = await require_call_row(conn, binding, call_id)
            if str(row["status"]) == "completed":
                raise ValueError("E_AGENT_BROKER_CALL_ALREADY_COMPLETED")
            await conn.execute(
                """
                UPDATE governed_agent_calls SET status = 'uncertain', normalized_reason = ?
                WHERE invocation_id = ? AND call_id = ?
                """,
                (normalized_reason, binding.invocation_id, call_id),
            )
            updated = await call_row(conn, binding.invocation_id, call_id)
            return call_record(updated or row)

        return await self._execute(_op)

    async def list_call_records(
        self,
        *,
        invocation_id: str,
    ) -> tuple[GovernedAgentBrokerCallRecord, ...]:
        async def _op(conn: aiosqlite.Connection) -> tuple[GovernedAgentBrokerCallRecord, ...]:
            cursor = await conn.execute(
                "SELECT * FROM governed_agent_calls WHERE invocation_id = ? ORDER BY rowid",
                (invocation_id,),
            )
            return tuple(call_record(row) for row in await cursor.fetchall())

        return await self._execute(_op)

    async def _execute(self, operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]]) -> ResultT:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await ensure_governed_agent_schema(conn)
                self._initialized = True
            result = await operation(conn)
            await conn.commit()
            return result
