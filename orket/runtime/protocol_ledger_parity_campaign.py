from __future__ import annotations

import aiosqlite
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


def _normalize_session_ids(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for raw in values:
        normalized = str(raw or "").strip()
        if not normalized:
            continue
        if normalized in deduped:
            continue
        deduped.append(normalized)
    return deduped


def _discover_protocol_session_ids(protocol_root: Path) -> list[str]:
    runs_root = (protocol_root / "runs").resolve()
    if not runs_root.exists():
        return []
    session_ids: list[str] = []
    for run_dir in sorted(runs_root.iterdir(), key=lambda item: item.name):
        if not run_dir.is_dir():
            continue
        if not (run_dir / "events.log").exists():
            continue
        session_ids.append(run_dir.name)
    return session_ids


async def _discover_sqlite_session_ids(*, sqlite_db: Path, limit: int) -> list[str]:
    if not sqlite_db.exists():
        return []
    rows: list[str] = []
    async with aiosqlite.connect(str(sqlite_db)) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'run_ledger' LIMIT 1")
        has_table = await cursor.fetchone()
        if not has_table:
            return []
        query = "SELECT session_id FROM run_ledger ORDER BY updated_at DESC, session_id ASC"
        params: tuple[Any, ...] = ()
        if limit > 0:
            query += " LIMIT ?"
            params = (int(limit),)
        cursor = await conn.execute(query, params)
        fetched = await cursor.fetchall()
    for row in fetched:
        value = str(row["session_id"] or "").strip()
        if value:
            rows.append(value)
    return rows


def _append_count(counter: dict[str, int], key: str) -> None:
    normalized = str(key or "").strip()
    if not normalized:
        return
    counter[normalized] = int(counter.get(normalized, 0)) + 1


def _sorted_counts(counter: dict[str, int]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _delta_label(*, field: str, left: Any, right: Any) -> str:
    left_text = str(left if left is not None else "null")
    right_text = str(right if right is not None else "null")
    return f"{field}:{left_text}->{right_text}"


def _campaign_summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in rows:
        summary.append(
            {
                "session_id": row["session_id"],
                "parity_ok": row["parity_ok"],
                "difference_count": row["difference_count"],
                "difference_fields": row["difference_fields"],
                "sqlite_digest": row["sqlite_digest"],
                "protocol_digest": row["protocol_digest"],
                "sqlite_status": row["sqlite_status"],
                "protocol_status": row["protocol_status"],
            }
        )
    return summary


async def compare_protocol_ledger_parity_campaign(
    *,
    sqlite_db: Path,
    protocol_root: Path,
    session_ids: list[str],
    discover_limit: int = 200,
) -> dict[str, Any]:
    requested_ids = _normalize_session_ids(session_ids)
    discovered_sqlite_ids = await _discover_sqlite_session_ids(
        sqlite_db=sqlite_db,
        limit=max(0, int(discover_limit)),
    )
    discovered_protocol_ids = _discover_protocol_session_ids(protocol_root)

    if requested_ids:
        campaign_ids = requested_ids
    else:
        campaign_ids = _normalize_session_ids(discovered_sqlite_ids + discovered_protocol_ids)

    if not campaign_ids:
        raise ValueError("No session ids available for parity campaign.")

    sqlite_repo = AsyncRunLedgerRepository(sqlite_db)
    protocol_repo = AsyncProtocolRunLedgerRepository(protocol_root)

    field_delta_counts: dict[str, int] = {}
    delta_signature_counts: dict[str, int] = {}
    status_delta_counts: dict[str, int] = {}
    mismatch_rows: list[dict[str, Any]] = []
    total_rows: list[dict[str, Any]] = []

    for session_id in campaign_ids:
        parity = await compare_run_ledger_rows(
            sqlite_repo=sqlite_repo,
            protocol_repo=protocol_repo,
            session_id=session_id,
        )
        differences = list(parity.get("differences") or [])
        difference_fields = [str(row.get("field") or "") for row in differences]
        sqlite_row = parity.get("sqlite_row") if isinstance(parity.get("sqlite_row"), dict) else {}
        protocol_row = parity.get("protocol_row") if isinstance(parity.get("protocol_row"), dict) else {}
        parity_ok = bool(parity.get("parity_ok", False))

        row = {
            "session_id": str(session_id),
            "parity_ok": parity_ok,
            "difference_count": len(differences),
            "difference_fields": difference_fields,
            "differences": differences,
            "sqlite_digest": parity.get("sqlite_digest"),
            "protocol_digest": parity.get("protocol_digest"),
            "sqlite_status": str(sqlite_row.get("status") or ""),
            "protocol_status": str(protocol_row.get("status") or ""),
        }
        total_rows.append(row)

        if parity_ok:
            continue

        mismatch_rows.append(row)
        for difference in differences:
            field = str(difference.get("field") or "")
            _append_count(field_delta_counts, field)
            _append_count(
                delta_signature_counts,
                _delta_label(field=field, left=difference.get("sqlite"), right=difference.get("protocol")),
            )
            if field == "status":
                _append_count(
                    status_delta_counts,
                    _delta_label(
                        field="status",
                        left=difference.get("sqlite"),
                        right=difference.get("protocol"),
                    ),
                )

    parity_ok_count = len([row for row in total_rows if bool(row.get("parity_ok"))])
    mismatch_count = len(total_rows) - parity_ok_count
    digest_mismatch_count = len(
        [
            row
            for row in total_rows
            if str(row.get("sqlite_digest") or "").strip()
            and str(row.get("protocol_digest") or "").strip()
            and str(row.get("sqlite_digest")) != str(row.get("protocol_digest"))
        ]
    )

    return {
        "sqlite_db": str(sqlite_db),
        "protocol_root": str(protocol_root),
        "candidate_count": len(campaign_ids),
        "parity_ok_count": parity_ok_count,
        "mismatch_count": mismatch_count,
        "all_match": mismatch_count == 0,
        "digest_mismatch_count": digest_mismatch_count,
        "requested_session_ids": requested_ids,
        "discovered_sqlite_session_ids": discovered_sqlite_ids,
        "discovered_protocol_session_ids": discovered_protocol_ids,
        "rows": _campaign_summary_rows(total_rows),
        "mismatches": _campaign_summary_rows(mismatch_rows),
        "compatibility_telemetry_delta": {
            "field_delta_counts": _sorted_counts(field_delta_counts),
            "delta_signature_counts": _sorted_counts(delta_signature_counts),
            "status_delta_counts": _sorted_counts(status_delta_counts),
        },
    }
