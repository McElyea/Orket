from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, TypeVar

import aiosqlite

from orket.adapters.storage.async_governed_agent_run_control_repository import agent_control_actions
from orket.adapters.storage.governed_agent_repository_support import (
    agent_digest,
    binding_from_json,
    decision_ref,
    invocation_row,
    iteration_snapshot,
    parent_matches,
)
from orket.application.services.governed_agent_ports import (
    GovernedAgentCancellationPublication,
    GovernedAgentDecisionPublication,
    GovernedAgentInvocationBinding,
    GovernedAgentIterationSnapshot,
)

ResultT = TypeVar("ResultT")


class _ConnectionExecutor(Protocol):
    async def __call__(
        self,
        operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]],
    ) -> ResultT: ...


class GovernedAgentDecisionStore:
    def __init__(self, execute: _ConnectionExecutor) -> None:
        self._execute = execute

    async def get_binding(self, *, invocation_id: str) -> GovernedAgentInvocationBinding | None:
        async def _op(conn: aiosqlite.Connection) -> GovernedAgentInvocationBinding | None:
            row = await invocation_row(conn, invocation_id)
            return None if row is None else binding_from_json(str(row["binding_json"]))

        return await self._execute(_op)

    async def get_request(self, *, invocation_id: str) -> Mapping[str, Any] | None:
        async def _op(conn: aiosqlite.Connection) -> Mapping[str, Any] | None:
            row = await invocation_row(conn, invocation_id)
            return None if row is None else dict(json.loads(str(row["request_json"])))

        return await self._execute(_op)

    async def record_interrupted(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        normalized_reason: str,
        provider_or_effect_uncertain: bool,
    ) -> str:
        async def _op(conn: aiosqlite.Connection) -> str:
            await conn.execute("BEGIN IMMEDIATE")
            row = await invocation_row(conn, binding.invocation_id)
            if row is None or binding_from_json(str(row["binding_json"])) != binding:
                raise ValueError("E_AGENT_INTERRUPTED_BINDING_STALE")
            await conn.execute(
                """
                UPDATE governed_agent_invocations
                SET state = 'interrupted', normalized_reason = ?, uncertainty = ?
                WHERE invocation_id = ?
                """,
                (normalized_reason, int(provider_or_effect_uncertain), binding.invocation_id),
            )
            return f"agent-interrupted:{binding.invocation_id}"

        return await self._execute(_op)

    async def cancel(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        cancellation_epoch: int,
        normalized_reason: str,
    ) -> GovernedAgentCancellationPublication:
        if cancellation_epoch <= binding.cancellation_epoch:
            return GovernedAgentCancellationPublication("conflict", None, None)

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentCancellationPublication:
            await conn.execute("BEGIN IMMEDIATE")
            row = await invocation_row(conn, binding.invocation_id)
            if row is None or binding_from_json(str(row["binding_json"])) != binding:
                return GovernedAgentCancellationPublication("stale", None, None)
            existing_epoch = row["cancelled_epoch"]
            if existing_epoch is not None:
                matches = int(existing_epoch) == cancellation_epoch and str(row["cancellation_reason"]) == normalized_reason
                if matches:
                    return GovernedAgentCancellationPublication(
                        "idempotent",
                        _cancellation_ref(binding.invocation_id, cancellation_epoch),
                        cancellation_epoch,
                    )
                return GovernedAgentCancellationPublication("conflict", None, None)
            await conn.execute(
                """
                UPDATE governed_agent_invocations
                SET state = 'cancelled', cancelled_epoch = ?, cancellation_reason = ?
                WHERE invocation_id = ?
                """,
                (cancellation_epoch, normalized_reason, binding.invocation_id),
            )
            return GovernedAgentCancellationPublication(
                "accepted",
                _cancellation_ref(binding.invocation_id, cancellation_epoch),
                cancellation_epoch,
            )

        return await self._execute(_op)

    async def publish(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        accepted_result_digest: str,
        decision_inputs: Mapping[str, Any],
        decision_payload: Mapping[str, Any],
    ) -> GovernedAgentDecisionPublication:
        inputs_json = json.dumps(dict(decision_inputs), sort_keys=True, separators=(",", ":"))
        decision_json = json.dumps(dict(decision_payload), sort_keys=True, separators=(",", ":"))
        decision_digest = agent_digest(json.loads(decision_json))

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentDecisionPublication:
            await conn.execute("BEGIN IMMEDIATE")
            row = await invocation_row(conn, binding.invocation_id)
            if row is None or binding_from_json(str(row["binding_json"])) != binding:
                return GovernedAgentDecisionPublication("stale", None, None)
            if not await parent_matches(conn, binding):
                return GovernedAgentDecisionPublication("stale", None, None)
            if row["decision_digest"] is not None:
                return _existing_decision(
                    row=row,
                    invocation_id=binding.invocation_id,
                    inputs_json=inputs_json,
                    decision_json=decision_json,
                    decision_digest=decision_digest,
                )
            if str(row["state"]) != "returned" or str(row["result_digest"]) != accepted_result_digest:
                return GovernedAgentDecisionPublication("conflict", None, None)
            controls = await agent_control_actions(conn, binding.invocation_id)
            if list(decision_inputs.get("operator_action_refs", [])) != [item.action_id for item in controls]:
                return GovernedAgentDecisionPublication("control_changed", None, None)
            await conn.execute(
                """
                UPDATE governed_agent_invocations
                SET state = 'decided', decision_inputs_json = ?, decision_json = ?, decision_digest = ?
                WHERE invocation_id = ?
                """,
                (inputs_json, decision_json, decision_digest, binding.invocation_id),
            )
            return GovernedAgentDecisionPublication(
                "accepted",
                decision_ref(binding.invocation_id),
                decision_digest,
            )

        return await self._execute(_op)

    async def get_snapshot(
        self,
        *,
        invocation_id: str,
    ) -> GovernedAgentIterationSnapshot | None:
        async def _op(conn: aiosqlite.Connection) -> GovernedAgentIterationSnapshot | None:
            row = await invocation_row(conn, invocation_id)
            return None if row is None else iteration_snapshot(row)

        return await self._execute(_op)

    async def list_snapshots(
        self,
        *,
        run_id: str,
    ) -> tuple[GovernedAgentIterationSnapshot, ...]:
        async def _op(conn: aiosqlite.Connection) -> tuple[GovernedAgentIterationSnapshot, ...]:
            cursor = await conn.execute(
                "SELECT * FROM governed_agent_invocations ORDER BY rowid",
            )
            snapshots = tuple(iteration_snapshot(row) for row in await cursor.fetchall())
            return tuple(snapshot for snapshot in snapshots if snapshot.binding.run_id == run_id)

        return await self._execute(_op)


def _existing_decision(
    *,
    row: aiosqlite.Row,
    invocation_id: str,
    inputs_json: str,
    decision_json: str,
    decision_digest: str,
) -> GovernedAgentDecisionPublication:
    if (
        str(row["decision_inputs_json"]) == inputs_json
        and str(row["decision_json"]) == decision_json
        and str(row["decision_digest"]) == decision_digest
    ):
        return GovernedAgentDecisionPublication(
            "idempotent",
            decision_ref(invocation_id),
            decision_digest,
        )
    return GovernedAgentDecisionPublication("conflict", None, None)


def _cancellation_ref(invocation_id: str, cancellation_epoch: int) -> str:
    return f"agent-cancellation:{invocation_id}:{cancellation_epoch}"
