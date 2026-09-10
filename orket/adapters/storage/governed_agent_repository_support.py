from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Literal, cast

import aiosqlite

from orket.application.services.governed_agent_ports import (
    GovernedAgentBrokerCallRecord,
    GovernedAgentInvocationBinding,
    GovernedAgentInvocationOutcome,
    GovernedAgentIterationSnapshot,
    GovernedAgentResultAcceptance,
)
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.domain import AttemptState, RunState
from orket_extension_sdk import canonical_digest_sha256


async def ensure_governed_agent_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS governed_agent_invocations (
            invocation_id TEXT PRIMARY KEY, binding_json TEXT NOT NULL, request_json TEXT NOT NULL,
            state TEXT NOT NULL, result_json TEXT, result_digest TEXT, normalized_reason TEXT,
            uncertainty INTEGER NOT NULL DEFAULT 0, decision_inputs_json TEXT,
            decision_json TEXT, decision_digest TEXT, cancelled_epoch INTEGER,
            cancellation_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS governed_agent_calls (
            invocation_id TEXT NOT NULL, call_id TEXT NOT NULL, operation TEXT NOT NULL, role TEXT,
            request_digest TEXT NOT NULL, status TEXT NOT NULL, reserved_input_tokens INTEGER NOT NULL,
            reserved_output_tokens INTEGER NOT NULL, charged_input_tokens INTEGER NOT NULL,
            charged_output_tokens INTEGER NOT NULL, result_digest TEXT, result_json TEXT,
            normalized_reason TEXT, PRIMARY KEY (invocation_id, call_id)
        );
        """
    )


async def parent_matches(
    conn: aiosqlite.Connection,
    binding: GovernedAgentInvocationBinding,
) -> bool:
    run_cursor = await conn.execute(
        "SELECT payload_json FROM control_plane_runs WHERE run_id = ?",
        (binding.run_id,),
    )
    attempt_cursor = await conn.execute(
        "SELECT payload_json FROM control_plane_attempts WHERE attempt_id = ?",
        (binding.attempt_id,),
    )
    step_cursor = await conn.execute(
        "SELECT payload_json FROM control_plane_steps WHERE step_id = ?",
        (binding.step_id,),
    )
    run_row = await run_cursor.fetchone()
    attempt_row = await attempt_cursor.fetchone()
    step_row = await step_cursor.fetchone()
    if run_row is None or attempt_row is None or step_row is None:
        return False
    run = RunRecord.model_validate_json(str(run_row["payload_json"]))
    attempt = AttemptRecord.model_validate_json(str(attempt_row["payload_json"]))
    step = StepRecord.model_validate_json(str(step_row["payload_json"]))
    return (
        run.lifecycle_state is RunState.EXECUTING
        and run.current_attempt_id == binding.attempt_id
        and run.policy_digest == binding.policy_digest
        and attempt.run_id == binding.run_id
        and attempt.attempt_state is AttemptState.EXECUTING
        and step.attempt_id == binding.attempt_id
        and step.input_ref == binding.request_digest
    )


async def budget_admits(
    conn: aiosqlite.Connection,
    invocation_id: str,
    request: dict[str, Any],
    *,
    operation: Literal["model.call.v1", "memory.query.v1"],
    role: str | None,
    input_tokens: int,
    output_tokens: int,
) -> bool:
    if operation != "model.call.v1":
        # V1 admits one bounded objective-memory query per iteration; iterations bound the run total.
        cursor = await conn.execute("SELECT COUNT(*) FROM governed_agent_calls WHERE invocation_id=? AND operation=?",
                                    (invocation_id, operation))
        return int((await cursor.fetchone())[0]) < 1
    budget = request["remaining_iteration_budget"]
    cursor = await conn.execute(
        """
        SELECT role, status, reserved_input_tokens, reserved_output_tokens,
               charged_input_tokens, charged_output_tokens
        FROM governed_agent_calls WHERE invocation_id = ? AND operation = 'model.call.v1'
        """,
        (invocation_id,),
    )
    rows = await cursor.fetchall()
    used_input = sum(_charged_or_reserved(row, "input") for row in rows)
    used_output = sum(_charged_or_reserved(row, "output") for row in rows)
    role_limit = {
        item["role"]: int(item["count"])
        for item in budget["per_role_model_calls"]
    }.get(role or "", 0)
    role_calls = sum(1 for row in rows if row["role"] == role)
    return (
        len(rows) < int(budget["model_calls"])
        and role_calls < role_limit
        and used_input + input_tokens <= int(budget["input_tokens"])
        and used_output + output_tokens <= int(budget["output_tokens"])
    )


def _charged_or_reserved(row: aiosqlite.Row, token_kind: str) -> int:
    prefix = "charged" if row["status"] == "completed" else "reserved"
    return int(row[f"{prefix}_{token_kind}_tokens"])


async def invocation_row(
    conn: aiosqlite.Connection,
    invocation_id: str,
) -> aiosqlite.Row | None:
    cursor = await conn.execute(
        "SELECT * FROM governed_agent_invocations WHERE invocation_id = ?",
        (invocation_id,),
    )
    return await cursor.fetchone()


async def call_row(
    conn: aiosqlite.Connection,
    invocation_id: str,
    call_id: str,
) -> aiosqlite.Row | None:
    cursor = await conn.execute(
        "SELECT * FROM governed_agent_calls WHERE invocation_id = ? AND call_id = ?",
        (invocation_id, call_id),
    )
    return await cursor.fetchone()


async def require_call_row(
    conn: aiosqlite.Connection,
    binding: GovernedAgentInvocationBinding,
    call_id: str,
) -> aiosqlite.Row:
    invocation = await invocation_row(conn, binding.invocation_id)
    if invocation is None or binding_from_json(str(invocation["binding_json"])) != binding:
        raise ValueError("E_AGENT_BROKER_BINDING_STALE")
    row = await call_row(conn, binding.invocation_id, call_id)
    if row is None:
        raise ValueError("E_AGENT_BROKER_CALL_MISSING")
    return row


async def host_model_receipts_match(
    conn: aiosqlite.Connection,
    invocation_id: str,
    result_payload: dict[str, Any],
) -> bool:
    cursor = await conn.execute(
        """
        SELECT status, result_json FROM governed_agent_calls
        WHERE invocation_id = ? AND operation = 'model.call.v1'
        """,
        (invocation_id,),
    )
    rows = await cursor.fetchall()
    if any(row["status"] != "completed" or row["result_json"] is None for row in rows):
        return False
    retained = {
        payload["receipt"]["call_id"]: payload["receipt"]
        for row in rows
        if isinstance((payload := json.loads(str(row["result_json"]))), dict)
    }
    child = {
        receipt["call_id"]: receipt
        for receipt in result_payload["model_receipts"]
    }
    return retained == child


def existing_acceptance(
    row: aiosqlite.Row,
    outcome: GovernedAgentInvocationOutcome,
) -> GovernedAgentResultAcceptance:
    expected_state = "returned" if outcome.status == "returned" else outcome.status
    state_matches = str(row["state"]) == expected_state or (
        outcome.status == "returned" and str(row["state"]) == "decided"
    )
    if str(row["result_digest"] or "") == str(outcome.result_digest or "") and state_matches:
        return GovernedAgentResultAcceptance(
            "idempotent",
            result_ref(outcome.binding.invocation_id),
            outcome.result_digest,
        )
    return GovernedAgentResultAcceptance("conflict", None, None)


def iteration_snapshot(row: aiosqlite.Row) -> GovernedAgentIterationSnapshot:
    return GovernedAgentIterationSnapshot(
        binding=binding_from_json(str(row["binding_json"])),
        state=str(row["state"]),
        request_payload=dict(json.loads(str(row["request_json"]))),
        result_payload=optional_payload(row["result_json"]),
        result_digest=str(row["result_digest"]) if row["result_digest"] is not None else None,
        decision_inputs=optional_payload(row["decision_inputs_json"]),
        decision_payload=optional_payload(row["decision_json"]),
        decision_digest=str(row["decision_digest"]) if row["decision_digest"] is not None else None,
        uncertainty=bool(row["uncertainty"]),
    )


def call_record(row: aiosqlite.Row) -> GovernedAgentBrokerCallRecord:
    operation = cast(Literal["model.call.v1", "memory.query.v1"], str(row["operation"]))
    status = cast(Literal["reserved", "completed", "uncertain"], str(row["status"]))
    return GovernedAgentBrokerCallRecord(
        invocation_id=str(row["invocation_id"]),
        call_id=str(row["call_id"]),
        operation=operation,
        request_digest=str(row["request_digest"]),
        status=status,
        reserved_input_tokens=int(row["reserved_input_tokens"]),
        reserved_output_tokens=int(row["reserved_output_tokens"]),
        charged_input_tokens=int(row["charged_input_tokens"]),
        charged_output_tokens=int(row["charged_output_tokens"]),
        result_digest=str(row["result_digest"]) if row["result_digest"] is not None else None,
        result_payload=optional_payload(row["result_json"]),
    )


def binding_json(binding: GovernedAgentInvocationBinding) -> str:
    return json.dumps(asdict(binding), sort_keys=True, separators=(",", ":"))


def binding_from_json(value: str) -> GovernedAgentInvocationBinding:
    return GovernedAgentInvocationBinding(**json.loads(value))


def optional_json(value: dict[str, Any] | None) -> str | None:
    return None if value is None else json.dumps(value, sort_keys=True, separators=(",", ":"))


def optional_payload(value: object) -> dict[str, Any] | None:
    return None if value is None else dict(json.loads(str(value)))


def agent_digest(value: dict[str, Any]) -> str:
    return "sha256:" + cast(str, canonical_digest_sha256(value))


def dispatch_ref(invocation_id: str) -> str:
    return f"agent-dispatch:{invocation_id}"


def result_ref(invocation_id: str) -> str:
    return f"agent-result:{invocation_id}"


def decision_ref(invocation_id: str) -> str:
    return f"agent-decision:{invocation_id}"


def call_ref(invocation_id: str, call_id: str) -> str:
    return f"agent-call:{invocation_id}:{call_id}"
