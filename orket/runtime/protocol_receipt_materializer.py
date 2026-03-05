from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Protocol

from orket.naming import sanitize_name


class _ProtocolLedgerWriter(Protocol):
    async def append_event(
        self,
        *,
        session_id: str,
        kind: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def append_receipt(
        self,
        *,
        session_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]: ...


def _protocol_receipt_files(*, workspace: Path, session_id: str) -> list[Path]:
    session_root = workspace / "observability" / sanitize_name(session_id)
    if not session_root.exists():
        return []
    files: list[Path] = []
    for issue_dir in sorted(session_root.iterdir(), key=lambda path: path.name):
        if not issue_dir.is_dir():
            continue
        for turn_dir in sorted(issue_dir.iterdir(), key=lambda path: path.name):
            if not turn_dir.is_dir():
                continue
            candidate = turn_dir / "protocol_receipts.log"
            if candidate.exists():
                files.append(candidate)
    return files


def _load_turn_receipts(*, workspace: Path, session_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_index, path in enumerate(_protocol_receipt_files(workspace=workspace, session_id=session_id), start=1):
        with path.open("r", encoding="utf-8") as handle:
            for line_index, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    continue
                row = dict(payload)
                row["_source_index"] = source_index
                row["_line_index"] = line_index
                rows.append(row)
    rows.sort(
        key=lambda row: (
            int(row.get("_source_index") or 0),
            int(row.get("_line_index") or 0),
            str(row.get("operation_id") or ""),
        )
    )
    return rows


def _event_payload_for_receipt(receipt: dict[str, Any], *, receipt_seq: int) -> dict[str, Any]:
    return {
        "operation_id": str(receipt.get("operation_id") or "").strip(),
        "step_id": str(receipt.get("step_id") or "").strip(),
        "tool": str(receipt.get("tool") or "").strip(),
        "tool_index": int(receipt.get("tool_index") or 0),
        "result": dict(receipt.get("execution_result") or {}),
        "receipt_seq": int(receipt_seq),
        "replayed": bool(receipt.get("replayed", False)),
    }


def _clean_receipt_payload(receipt: dict[str, Any], *, receipt_seq: int, event_seq: int) -> dict[str, Any]:
    payload = dict(receipt)
    payload.pop("_source_index", None)
    payload.pop("_line_index", None)
    # Recompute digest at append time with the finalized event cross-link.
    payload.pop("receipt_digest", None)
    payload["receipt_seq"] = int(receipt_seq)
    payload["event_seq_range"] = [int(event_seq), int(event_seq)]
    return payload


async def materialize_protocol_receipts(
    *,
    workspace: Path,
    session_id: str,
    run_ledger: _ProtocolLedgerWriter,
) -> dict[str, Any]:
    rows = await asyncio.to_thread(
        _load_turn_receipts,
        workspace=workspace,
        session_id=session_id,
    )
    if not rows:
        return {
            "session_id": str(session_id),
            "source_receipts": 0,
            "materialized_receipts": 0,
            "reused_receipts": 0,
            "status": "empty",
        }

    materialized = 0
    reused = 0
    for index, row in enumerate(rows, start=1):
        receipt_seq = int(index)
        event = await run_ledger.append_event(
            session_id=session_id,
            kind="operation_result",
            payload=_event_payload_for_receipt(row, receipt_seq=receipt_seq),
        )
        event_reused = str(event.get("kind") or "") == "operation_rejected" and bool(event.get("idempotent_reuse", False))
        event_seq = int(event.get("event_seq") or event.get("winner_event_seq") or 0)
        await run_ledger.append_receipt(
            session_id=session_id,
            receipt=_clean_receipt_payload(row, receipt_seq=receipt_seq, event_seq=event_seq),
        )
        if event_reused:
            reused += 1
        else:
            materialized += 1

    return {
        "session_id": str(session_id),
        "source_receipts": len(rows),
        "materialized_receipts": materialized,
        "reused_receipts": reused,
        "status": "ok",
    }
