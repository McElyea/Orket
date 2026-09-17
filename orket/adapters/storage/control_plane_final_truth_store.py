"""One immutable terminal truth per run, without choosing among old conflicts."""
from __future__ import annotations

import aiosqlite

from orket.core.contracts.control_plane_models import FinalTruthRecord
from orket.core.domain.control_plane_final_truth import ControlPlaneFinalTruthError

side_effecting = True


class FinalTruthReadLimitError(ValueError):
    """The caller's bounded history read cannot include this retained truth."""


async def read_final_truth(
    conn: aiosqlite.Connection, *, run_id: str, max_bytes: int | None = None,
) -> FinalTruthRecord | None:
    async with conn.execute(
        'SELECT final_truth_record_id, run_id, payload_json FROM final_truth_records WHERE run_id = ? LIMIT 2',
        (run_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    if max_bytes is not None and sum(len(str(value).encode('utf-8')) for row in rows for value in row) > max_bytes:
        raise FinalTruthReadLimitError('final_truth_read_resource_limit')
    if len(rows) > 1:
        raise ControlPlaneFinalTruthError('E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:multiple_final_truth_records')
    if not rows:
        return None
    row = rows[0]
    record = FinalTruthRecord.model_validate_json(row[2])
    if record.final_truth_record_id != row[0] or record.run_id != row[1] or record.run_id != run_id:
        raise ControlPlaneFinalTruthError('E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:truth_identity')
    return record


async def save_final_truth(conn: aiosqlite.Connection, *, record: FinalTruthRecord) -> FinalTruthRecord:
    # The owning repository commits. Borrowed control-plane transactions already
    # hold the writer; standalone callers acquire it before comparing run identity.
    if not conn.in_transaction:
        await conn.execute('BEGIN IMMEDIATE')
    existing = await read_final_truth(conn, run_id=record.run_id)
    if existing is not None:
        if existing != record:
            raise ControlPlaneFinalTruthError('E_CONTROL_PLANE_FINAL_TRUTH_IDENTITY_CONFLICT')
        return existing
    try:
        await conn.execute(
            'INSERT INTO final_truth_records (final_truth_record_id, run_id, payload_json) VALUES (?, ?, ?)',
            (record.final_truth_record_id, record.run_id, record.model_dump_json()),
        )
    except aiosqlite.IntegrityError as exc:
        raise ControlPlaneFinalTruthError('E_CONTROL_PLANE_FINAL_TRUTH_IDENTITY_CONFLICT') from exc
    return record
