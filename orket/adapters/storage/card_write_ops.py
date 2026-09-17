"""Card writes executed inside the repository's SQLite writer transaction."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from orket.core.contracts.card_completion_commit import (
    SUCCESSFUL_CARD_STATUSES,
    CardCompletionAuthority,
    CardCompletionContext,
    CardCompletionReceipt,
    CardCompletionRejected,
    CardCompletionRequest,
    card_completion_inputs,
    require_current_completion_receipt,
)
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus

from .card_record_codec import deserialize_card_row

side_effecting = True


async def load_card(conn: aiosqlite.Connection, card_id: str) -> IssueRecord | None:
    cursor = await conn.execute("SELECT * FROM issues WHERE id = ?", (card_id,))
    row = await cursor.fetchone()
    return IssueRecord.model_validate(deserialize_card_row(dict(row))) if row else None


async def read_completion_receipt(
    conn: aiosqlite.Connection, card_id: str,
) -> tuple[IssueRecord, CardCompletionReceipt] | None:
    cursor = await conn.execute(
        "SELECT issues.*, c.receipt_json FROM issues LEFT JOIN card_completion_commits c "
        "ON c.completion_ref = issues.completion_ref WHERE issues.id = ?", (card_id,),
    )
    row = await cursor.fetchone()
    if row is None or row["status"] not in SUCCESSFUL_CARD_STATUSES or row["completion_ref"] is None:
        return None
    if row["receipt_json"] is None:
        raise CardCompletionRejected("E_CARD_COMPLETION_RECEIPT_MISSING")
    receipt = CardCompletionReceipt.model_validate_json(row["receipt_json"])
    record = IssueRecord.model_validate(deserialize_card_row(dict(row)))
    require_current_completion_receipt(record, receipt)
    return record, receipt


async def save_card(conn: aiosqlite.Connection, record: IssueRecord) -> None:
    current = await load_card(conn, record.id)
    same_inputs = current is not None and card_completion_inputs(current) == card_completion_inputs(record)
    same_status = current is not None and current.status == record.status
    if record.status.value in SUCCESSFUL_CARD_STATUSES and not (same_inputs and same_status):
        raise CardCompletionRejected("E_CARD_COMPLETION_SAVE_REQUIRES_REVIEW")
    values = record.model_dump(mode="json", exclude={
        "completion_generation", "completion_context", "completion_ref",
    })
    values["summary"] = record.summary or "Unnamed Unit"
    values["created_at"] = record.created_at or (current.created_at if current else None) or datetime.now(UTC).isoformat()
    if current is not None:
        previous = current.model_dump(mode="json")
        values = {column: value for column, value in values.items() if value != previous[column] and column != "id"}
    for field in ("verification", "metrics", "params", "depends_on"):
        if field in values:
            values[field + "_json"] = json.dumps(values.pop(field), allow_nan=False)
    if current is None:
        columns = ", ".join(values)
        await conn.execute(
            f"INSERT INTO issues ({columns}) VALUES ({', '.join('?' for _ in values)})", tuple(values.values()),
        )
    else:
        if not (same_inputs and same_status):
            values.update(completion_context_json=None, completion_ref=None,
                          completion_generation=current.completion_generation + 1)
        if values:
            assignments = ", ".join(f"{column} = ?" for column in values)
            await conn.execute(f"UPDATE issues SET {assignments} WHERE id = ?", (*values.values(), record.id))


async def begin_completion_attempt(conn: aiosqlite.Connection, context: CardCompletionContext) -> None:
    current = await load_card(conn, context.card_id)
    if current is None:
        raise CardCompletionRejected("E_CARD_COMPLETION_CARD_MISSING")
    if current.status.value in SUCCESSFUL_CARD_STATUSES:
        raise CardCompletionRejected("E_CARD_COMPLETION_REOPEN_REQUIRED")
    if (context.generation != current.completion_generation + 1
            or context.workload_inputs_json != card_completion_inputs(current)):
        raise CardCompletionRejected("E_CARD_COMPLETION_ATTEMPT_STALE")
    await conn.execute(
        "UPDATE issues SET completion_generation = ?, completion_context_json = ?, completion_ref = NULL WHERE id = ?",
        (context.generation, context.model_dump_json(), context.card_id),
    )


async def authorize_card_completion(
    conn: aiosqlite.Connection, *, current: IssueRecord, status: CardStatus,
    assignee: str | None, request: CardCompletionRequest | None, authority: CardCompletionAuthority | None,
) -> CardCompletionReceipt:
    context = current.completion_context
    if authority is None:
        raise CardCompletionRejected("E_CARD_COMPLETION_AUTHORITY_MISSING")
    if not isinstance(request, CardCompletionRequest) or context is None:
        raise CardCompletionRejected("E_CARD_COMPLETION_EVIDENCE_REQUIRED")
    if (context.digest != request.context_digest or context.card_id != current.id
            or context.generation != current.completion_generation
            or context.workload_inputs_json != card_completion_inputs(current)
            or (assignee and assignee != current.assignee)):
        raise CardCompletionRejected("E_CARD_COMPLETION_CONTEXT_STALE")
    decision = await authority.authorize_completion(record=current, context=context, request=request)
    if not decision.sufficient:
        raise CardCompletionRejected("E_CARD_COMPLETION_ACCEPTANCE_REQUIRED", decision)
    receipt = CardCompletionReceipt(context=context, request=request, target_status=status.value, decision=decision)
    payload = receipt.model_dump_json()
    await conn.execute(
        "INSERT OR IGNORE INTO card_completion_commits VALUES (?, ?, ?, ?, ?)",
        (receipt.digest, current.id, status.value, context.model_dump_json(), payload),
    )
    cursor = await conn.execute("SELECT receipt_json FROM card_completion_commits WHERE completion_ref = ?", (receipt.digest,))
    if (await cursor.fetchone())[0] != payload:
        raise CardCompletionRejected("E_CARD_COMPLETION_RECEIPT_COLLISION")
    return receipt


async def update_card_status(
    conn: aiosqlite.Connection, *, card_id: str, status: CardStatus, assignee: str | None,
    reason: str | None, metadata: dict[str, Any] | None, request: CardCompletionRequest | None,
    authority: CardCompletionAuthority | None,
) -> CardCompletionReceipt | None:
    current = await load_card(conn, card_id)
    if current is None:
        raise ValueError(f"Card not found: {card_id}")
    completion_ref = current.completion_ref
    receipt = None
    successful = status.value in SUCCESSFUL_CARD_STATUSES
    if successful:
        receipt = await authorize_card_completion(
            conn, current=current, status=status, assignee=assignee, request=request, authority=authority,
        )
        completion_ref = receipt.digest
    changed = status != current.status or (assignee and assignee != current.assignee)
    if successful and not changed and completion_ref == current.completion_ref:
        return receipt
    context = current.completion_context
    generation = current.completion_generation
    if not successful and changed:
        context, completion_ref, generation = None, None, generation + 1
    await conn.execute(
        "UPDATE issues SET status = ?, assignee = ?, completion_context_json = ?, completion_ref = ?, "
        "completion_generation = ? WHERE id = ?",
        (status.value, assignee or current.assignee, context.model_dump_json() if context else None,
         completion_ref, generation, card_id),
    )
    action = f"Set Status to '{status.value}' (from '{current.status.value}')"
    if reason:
        action += f" reason='{reason}'"
    if metadata:
        action += f" meta={json.dumps(metadata, ensure_ascii=False, sort_keys=True)}"
    if completion_ref:
        action += f" completion_ref='{completion_ref}'"
    await conn.execute(
        "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
        (card_id, assignee or "system", action),
    )
    return receipt
