from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.storage.control_plane_final_truth_store import FinalTruthReadLimitError, read_final_truth
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.contracts.governed_agent_replay import GovernedAgentReplayEvidence

_MAX_ROWS = 10000
_MAX_BYTES = 64 * 1024 * 1024


side_effecting = False


class ReplayEvidenceError(ValueError):
    """A bounded diagnostic that contains no retained request or secret data."""


class GovernedAgentReplayStore:
    """Read-only, transaction-consistent evidence, including independent step records."""

    side_effecting = False

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)

    async def read_replay_evidence(self, *, run_id: str) -> GovernedAgentReplayEvidence:
        path = await asyncio.to_thread(self._path.resolve)
        if not await asyncio.to_thread(path.exists):
            return GovernedAgentReplayEvidence()
        try:
            async with aiosqlite.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute("PRAGMA query_only = ON")
                await conn.execute("BEGIN")
                return await _read_evidence(conn, run_id)
        except ReplayEvidenceError as exc:
            return GovernedAgentReplayEvidence(diagnostics=(str(exc),))
        except FinalTruthReadLimitError:
            return GovernedAgentReplayEvidence(diagnostics=("replay_evidence_resource_limit",))
        except (aiosqlite.DatabaseError, OSError, ValueError, TypeError, KeyError) as exc:
            return GovernedAgentReplayEvidence(diagnostics=(f"evidence_unreadable:{type(exc).__name__}",))


async def _rows(conn: aiosqlite.Connection, sql: str, parameters: tuple = ()) -> list[aiosqlite.Row]:
    async with conn.execute(sql, parameters) as cursor:
        rows = await cursor.fetchmany(_MAX_ROWS + 1)
    if len(rows) > _MAX_ROWS or sum(len(str(value).encode("utf-8")) for row in rows for value in row) > _MAX_BYTES:
        raise ReplayEvidenceError("replay_evidence_resource_limit")
    return rows


def _object(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("replay_record_not_object")
    return value


def _record(row: aiosqlite.Row, model: Any, *identity_fields: str) -> dict[str, Any]:
    payload = model.model_validate_json(row["payload_json"]).model_dump(mode="json")
    if any(payload.get(field) != row[field] for field in identity_fields):
        raise ValueError("replay_record_identity_mismatch")
    return payload


async def _read_evidence(conn: aiosqlite.Connection, run_id: str) -> GovernedAgentReplayEvidence:
    tables = {row[0] for row in await _rows(conn, "SELECT name FROM sqlite_master WHERE type='table'")}
    if "control_plane_runs" not in tables:
        return GovernedAgentReplayEvidence(diagnostics=("run_inventory_missing",))
    runs = await _rows(conn, "SELECT * FROM control_plane_runs WHERE run_id = ?", (run_id,))
    if not runs:
        return GovernedAgentReplayEvidence()
    run = _record(runs[0], RunRecord, "run_id")
    if not {"control_plane_attempts", "control_plane_steps"}.issubset(tables):
        return GovernedAgentReplayEvidence(run=run, diagnostics=("step_inventory_missing",))
    attempts = tuple(_record(row, AttemptRecord, "attempt_id", "run_id") for row in await _rows(
        conn, "SELECT * FROM control_plane_attempts WHERE run_id = ? ORDER BY attempt_ordinal", (run_id,),
    ))
    steps = tuple(_record(row, StepRecord, "step_id", "attempt_id") for row in await _rows(
        conn, "SELECT s.* FROM control_plane_steps s JOIN control_plane_attempts a "
        "ON a.attempt_id = s.attempt_id WHERE a.run_id = ? ORDER BY s.rowid", (run_id,),
    ))
    iterations = await _iterations(conn, run_id) if "governed_agent_invocations" in tables else ()
    truth = None
    if "final_truth_records" in tables:
        record = await read_final_truth(conn, run_id=run_id, max_bytes=_MAX_BYTES)
        truth = record.model_dump(mode="json") if record is not None else None
    return GovernedAgentReplayEvidence(run, attempts, steps, iterations, truth)


async def _iterations(conn: aiosqlite.Connection, run_id: str) -> tuple[dict[str, Any], ...]:
    # Legacy rows have no indexed run column. Invalid binding JSON must fail closed.
    rows = await _rows(conn, "SELECT * FROM governed_agent_invocations WHERE "
                       "CASE WHEN json_valid(binding_json) THEN json_extract(binding_json, '$.run_id') = ? "
                       "ELSE 1 END ORDER BY rowid", (run_id,))
    records = []
    for row in rows:
        record = dict(row)
        try:
            for field in ("binding", "request", "result", "decision_inputs", "decision"):
                raw = record.pop(field + "_json")
                record[field] = None if raw is None else _object(raw)
        except (ValueError, TypeError, KeyError):
            record = {"invocation_id": row["invocation_id"], "evidence_error": "iteration_record_invalid"}
        records.append(record)
    return tuple(records)
