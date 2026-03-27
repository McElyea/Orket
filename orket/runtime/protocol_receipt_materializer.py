from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Protocol

from orket.application.services.turn_tool_control_plane_support import effect_id_for
from orket.application.workflows.tool_invocation_contracts import (
    compute_tool_call_hash,
    normalize_tool_invocation_manifest,
)
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

    async def list_events(self, session_id: str) -> list[dict[str, Any]]: ...


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


def _resolve_receipt_contract(
    *,
    receipt: dict[str, Any],
    session_id: str,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    manifest = normalize_tool_invocation_manifest(
        manifest=receipt.get("tool_invocation_manifest")
        if isinstance(receipt.get("tool_invocation_manifest"), dict)
        else None,
        run_id=str(session_id),
        tool_name_fallback=str(receipt.get("tool") or ""),
    )
    if manifest is None:
        raise ValueError("E_TOOL_INVOCATION_MANIFEST_REQUIRED")
    tool_args = dict(receipt.get("tool_args") or {}) if isinstance(receipt.get("tool_args"), dict) else {}
    observed_hash = str(receipt.get("tool_call_hash") or "").strip()
    if not observed_hash:
        raise ValueError("E_TOOL_CALL_HASH_REQUIRED")
    expected_hash = compute_tool_call_hash(
        tool_name=str(manifest.get("tool_name") or ""),
        tool_args=tool_args,
        tool_contract_version=str(manifest.get("tool_contract_version") or ""),
        capability_profile=str(manifest.get("capability_profile") or ""),
    )
    if observed_hash != expected_hash:
        raise ValueError("E_TOOL_CALL_HASH_MISMATCH")
    return manifest, observed_hash, tool_args


def _tool_call_payload_for_receipt(
    receipt: dict[str, Any],
    *,
    receipt_seq: int,
    manifest: dict[str, Any],
    tool_call_hash: str,
    tool_args: dict[str, Any],
) -> dict[str, Any]:
    return {
        "operation_id": str(receipt.get("operation_id") or "").strip(),
        "step_id": str(receipt.get("step_id") or "").strip(),
        "tool": str(receipt.get("tool") or "").strip(),
        "tool_index": int(receipt.get("tool_index") or 0),
        "tool_args": dict(tool_args),
        "tool_invocation_manifest": dict(manifest),
        "tool_call_hash": str(tool_call_hash),
        "receipt_seq": int(receipt_seq),
        "replayed": bool(receipt.get("replayed", False)),
        "projection_source": "observability.protocol_receipts.log",
        "projection_only": True,
    }


def _tool_result_payload_for_receipt(
    receipt: dict[str, Any],
    *,
    receipt_seq: int,
    call_sequence_number: int,
    manifest: dict[str, Any],
    tool_call_hash: str,
) -> dict[str, Any]:
    payload = {
        "operation_id": str(receipt.get("operation_id") or "").strip(),
        "step_id": str(receipt.get("step_id") or "").strip(),
        "tool": str(receipt.get("tool") or "").strip(),
        "tool_index": int(receipt.get("tool_index") or 0),
        "result": dict(receipt.get("execution_result") or {}),
        "call_sequence_number": int(call_sequence_number),
        "tool_invocation_manifest": dict(manifest),
        "tool_call_hash": str(tool_call_hash),
        "receipt_seq": int(receipt_seq),
        "replayed": bool(receipt.get("replayed", False)),
        "projection_source": "observability.protocol_receipts.log",
        "projection_only": True,
    }
    effect_projection = _control_plane_effect_projection(receipt=receipt, manifest=manifest)
    if effect_projection is not None:
        payload["control_plane_effect_projection"] = effect_projection
    return payload


def _control_plane_effect_projection(
    *,
    receipt: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any] | None:
    control_plane_run_id = str(manifest.get("control_plane_run_id") or "").strip()
    operation_id = str(receipt.get("operation_id") or "").strip()
    if not control_plane_run_id.startswith("turn-tool-run:") or not operation_id:
        return None
    payload: dict[str, Any] = {
        "projection_only": True,
        "authority_surface": "control_plane_effect_journal",
        "run_id": control_plane_run_id,
        "effect_id": effect_id_for(operation_id=operation_id),
    }
    control_plane_attempt_id = str(manifest.get("control_plane_attempt_id") or "").strip()
    if control_plane_attempt_id:
        payload["attempt_id"] = control_plane_attempt_id
    return payload


def _clean_receipt_payload(
    receipt: dict[str, Any],
    *,
    receipt_seq: int,
    event_seq_range: list[int],
) -> dict[str, Any]:
    payload = dict(receipt)
    payload.pop("_source_index", None)
    payload.pop("_line_index", None)
    # Recompute digest at append time with the finalized event cross-link.
    payload.pop("receipt_digest", None)
    payload["receipt_seq"] = int(receipt_seq)
    payload["event_seq_range"] = [int(event_seq_range[0]), int(event_seq_range[1])]
    return payload


def _operation_event_ranges(events: list[dict[str, Any]]) -> dict[str, list[int]]:
    rows: dict[str, list[int]] = {}
    for event in events:
        kind = str(event.get("kind") or "")
        if kind not in {"operation_result", "tool_result"}:
            continue
        operation_id = str(event.get("operation_id") or "").strip()
        if not operation_id:
            continue
        result_seq = int(event.get("event_seq") or event.get("sequence_number") or 0)
        if result_seq <= 0:
            continue
        call_seq = int(event.get("call_sequence_number") or 0)
        start_seq = call_seq if call_seq > 0 else result_seq
        rows[operation_id] = [start_seq, result_seq]
    return rows


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
    existing_ranges = _operation_event_ranges(await run_ledger.list_events(str(session_id)))
    for index, row in enumerate(rows, start=1):
        receipt_seq = int(index)
        operation_id = str(row.get("operation_id") or "").strip()
        if not operation_id:
            raise ValueError("E_OPERATION_ID_REQUIRED")
        existing_range = existing_ranges.get(operation_id)
        if existing_range is not None:
            await run_ledger.append_receipt(
                session_id=session_id,
                receipt=_clean_receipt_payload(row, receipt_seq=receipt_seq, event_seq_range=existing_range),
            )
            reused += 1
            continue

        manifest, tool_call_hash, tool_args = _resolve_receipt_contract(
            receipt=row,
            session_id=str(session_id),
        )
        call_event = await run_ledger.append_event(
            session_id=session_id,
            kind="tool_call",
            payload=_tool_call_payload_for_receipt(
                row,
                receipt_seq=receipt_seq,
                manifest=manifest,
                tool_call_hash=tool_call_hash,
                tool_args=tool_args,
            ),
        )
        if str(call_event.get("kind") or "") == "operation_rejected" and bool(
            call_event.get("idempotent_reuse", False)
        ):
            winner_seq = int(call_event.get("winner_event_seq") or 0)
            winner_range = [winner_seq, winner_seq]
            existing_ranges[operation_id] = winner_range
            await run_ledger.append_receipt(
                session_id=session_id,
                receipt=_clean_receipt_payload(row, receipt_seq=receipt_seq, event_seq_range=winner_range),
            )
            reused += 1
            continue
        if str(call_event.get("kind") or "") != "tool_call":
            raise ValueError(str(call_event.get("error_code") or "E_TOOL_CALL_APPEND_REJECTED"))
        call_sequence_number = int(call_event.get("event_seq") or call_event.get("sequence_number") or 0)
        if call_sequence_number <= 0:
            raise ValueError("E_TOOL_CALL_SEQUENCE_INVALID")

        result_event = await run_ledger.append_event(
            session_id=session_id,
            kind="operation_result",
            payload=_tool_result_payload_for_receipt(
                row,
                receipt_seq=receipt_seq,
                call_sequence_number=call_sequence_number,
                manifest=manifest,
                tool_call_hash=tool_call_hash,
            ),
        )
        if str(result_event.get("kind") or "") != "operation_result":
            raise ValueError(str(result_event.get("error_code") or "E_TOOL_RESULT_APPEND_REJECTED"))
        result_sequence_number = int(result_event.get("event_seq") or result_event.get("sequence_number") or 0)
        if result_sequence_number <= 0:
            raise ValueError("E_TOOL_RESULT_SEQUENCE_INVALID")
        event_seq_range = [call_sequence_number, result_sequence_number]
        existing_ranges[operation_id] = event_seq_range
        await run_ledger.append_receipt(
            session_id=session_id,
            receipt=_clean_receipt_payload(row, receipt_seq=receipt_seq, event_seq_range=event_seq_range),
        )
        materialized += 1

    return {
        "session_id": str(session_id),
        "source_receipts": len(rows),
        "materialized_receipts": materialized,
        "reused_receipts": reused,
        "status": "ok",
    }
