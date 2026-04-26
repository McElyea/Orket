from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from orket.core.domain.outward_run_events import LedgerEvent

SCHEMA_VERSION = "ledger_export.v1"
GENESIS_CHAIN_HASH = "GENESIS"
LEDGER_EXPORT_REQUESTED = "ledger_export_requested"

EVENT_GROUPS: dict[str, frozenset[str] | None] = {
    "proposals": frozenset({"proposal_made", "proposal_pending_approval"}),
    "decisions": frozenset({"proposal_approved", "proposal_denied", "proposal_expired"}),
    "commitments": frozenset({"commitment_recorded"}),
    "tools": frozenset({"tool_invoked"}),
    "audit": frozenset({LEDGER_EXPORT_REQUESTED}),
    "all": None,
}


class LedgerExportValidationError(ValueError):
    pass


def normalize_event_groups(types: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    raw_groups = tuple(str(item or "").strip().lower() for item in (types or ()) if str(item or "").strip())
    if not raw_groups:
        return ("all",)
    if "all" in raw_groups:
        return ("all",)
    invalid = sorted({item for item in raw_groups if item not in EVENT_GROUPS})
    if invalid:
        raise LedgerExportValidationError(f"Unsupported ledger event group(s): {', '.join(invalid)}")
    return tuple(dict.fromkeys(raw_groups))


def event_group(event_type: str) -> str:
    for group, event_types in EVENT_GROUPS.items():
        if event_types is not None and event_type in event_types:
            return group
    return "all"


def event_hash_for(event: LedgerEvent) -> str:
    return hashlib.sha256(_canonical_json(canonical_event(event)).encode("utf-8")).hexdigest()


def chain_hash_for(previous_chain_hash: str, event_hash: str) -> str:
    return hashlib.sha256(f"{previous_chain_hash}\n{event_hash}".encode()).hexdigest()


def canonical_event(event: LedgerEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "run_id": event.run_id,
        "turn": event.turn,
        "agent_id": event.agent_id,
        "at": event.at,
        "payload": event.payload,
    }


def verify_ledger_export(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be ledger_export.v1")
    export_scope = str(payload.get("export_scope") or "")
    if export_scope not in {"all", "partial_view"}:
        errors.append("export_scope must be all or partial_view")
    canonical = payload.get("canonical")
    if not isinstance(canonical, Mapping):
        canonical = {}
        errors.append("canonical must be an object")
    canonical_count = _int_field(canonical, "event_count", errors)
    ledger_hash = str(canonical.get("ledger_hash") or "")
    if not ledger_hash:
        errors.append("canonical.ledger_hash is required")
    if canonical.get("genesis") not in {None, GENESIS_CHAIN_HASH}:
        errors.append("canonical.genesis must be GENESIS")

    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raw_events = []
        errors.append("events must be an array")

    positions: set[int] = set()
    disclosed_chains: dict[int, str] = {}
    previous_position = 0
    previous_disclosed_chain = GENESIS_CHAIN_HASH
    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping):
            errors.append("event entry must be an object")
            continue
        position = _int_field(raw_event, "position", errors)
        if position <= previous_position:
            errors.append("events must be ordered by ascending position")
        if position in positions:
            errors.append(f"duplicate event position: {position}")
        positions.add(position)
        previous_chain_hash = str(raw_event.get("previous_chain_hash") or "")
        event = _event_from_export(raw_event)
        expected_event_hash = event_hash_for(event)
        expected_chain_hash = chain_hash_for(previous_chain_hash, expected_event_hash)
        if raw_event.get("event_hash") != expected_event_hash:
            errors.append(f"event_hash mismatch at position {position}")
        if raw_event.get("chain_hash") != expected_chain_hash:
            errors.append(f"chain_hash mismatch at position {position}")
        if export_scope == "all":
            if position != previous_position + 1:
                errors.append(f"full export missing position {previous_position + 1}")
            if previous_chain_hash != previous_disclosed_chain:
                errors.append(f"previous_chain_hash mismatch at position {position}")
        elif position == previous_position + 1 and previous_chain_hash != previous_disclosed_chain:
            errors.append(f"disclosed chain link mismatch at position {position}")
        disclosed_chains[position] = expected_chain_hash
        previous_disclosed_chain = expected_chain_hash
        previous_position = position

    if export_scope == "all":
        _verify_full_export(raw_events, canonical_count, ledger_hash, previous_disclosed_chain, errors)
    else:
        _verify_partial_export(payload, canonical_count, ledger_hash, positions, disclosed_chains, errors)

    result = "invalid" if errors else ("valid" if export_scope == "all" else "partial_valid")
    return {
        "schema_version": SCHEMA_VERSION,
        "result": result,
        "export_scope": export_scope or None,
        "run_id": payload.get("run_id"),
        "ledger_hash": ledger_hash or None,
        "event_count": canonical_count,
        "checked_event_count": len(raw_events),
        "errors": errors,
    }


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _event_from_export(payload: Mapping[str, Any]) -> LedgerEvent:
    raw_payload = payload.get("payload")
    return LedgerEvent(
        event_id=str(payload.get("event_id") or ""),
        event_type=str(payload.get("event_type") or ""),
        run_id=str(payload.get("run_id") or ""),
        turn=payload.get("turn") if payload.get("turn") is None else int(payload.get("turn")),
        agent_id=payload.get("agent_id") if payload.get("agent_id") is None else str(payload.get("agent_id")),
        at=str(payload.get("at") or ""),
        payload=dict(raw_payload) if isinstance(raw_payload, Mapping) else {},
    )


def _verify_full_export(
    raw_events: list[Any],
    canonical_count: int,
    ledger_hash: str,
    previous_disclosed_chain: str,
    errors: list[str],
) -> None:
    if len(raw_events) != canonical_count:
        errors.append("full export event count does not match canonical event_count")
    if canonical_count == 0 and ledger_hash != GENESIS_CHAIN_HASH:
        errors.append("empty ledger_hash must be GENESIS")
    if canonical_count > 0 and previous_disclosed_chain != ledger_hash:
        errors.append("full export final chain_hash does not match canonical ledger_hash")


def _verify_partial_export(
    payload: Mapping[str, Any],
    canonical_count: int,
    ledger_hash: str,
    positions: set[int],
    disclosed_chains: dict[int, str],
    errors: list[str],
) -> None:
    if positions and max(positions) > canonical_count:
        errors.append("disclosed event position exceeds canonical event_count")
    spans = payload.get("omitted_spans")
    if not isinstance(spans, list):
        errors.append("partial_view omitted_spans must be an array")
        return
    omitted_positions = set(range(1, canonical_count + 1)) - positions
    anchored_positions: set[int] = set()
    for raw_span in spans:
        if not isinstance(raw_span, Mapping):
            errors.append("omitted span must be an object")
            continue
        start = _int_field(raw_span, "from_position", errors)
        end = _int_field(raw_span, "to_position", errors)
        if start > end:
            errors.append(f"omitted span {start}-{end} is inverted")
        if start < 1 or end > canonical_count:
            errors.append(f"omitted span {start}-{end} is outside canonical event_count")
        if any(position in positions for position in range(start, end + 1)):
            errors.append(f"omitted span {start}-{end} overlaps disclosed events")
        anchored_positions.update(range(start, end + 1))
        previous_anchor = GENESIS_CHAIN_HASH if start == 1 else disclosed_chains.get(start - 1)
        if previous_anchor is not None and raw_span.get("previous_chain_hash") != previous_anchor:
            errors.append(f"omitted span {start}-{end} previous anchor mismatch")
        next_position = end + 1
        if next_position in positions:
            next_event = next(item for item in payload["events"] if item["position"] == next_position)
            if next_event.get("previous_chain_hash") != raw_span.get("next_chain_hash"):
                errors.append(f"omitted span {start}-{end} next anchor mismatch")
        if end == canonical_count and raw_span.get("next_chain_hash") != ledger_hash:
            errors.append(f"omitted span {start}-{end} does not anchor canonical ledger_hash")
    if anchored_positions != omitted_positions:
        errors.append("partial_view omitted_spans do not cover exactly the omitted event positions")


def _int_field(payload: Mapping[str, Any], field: str, errors: list[str]) -> int:
    value = payload.get(field)
    if isinstance(value, bool):
        errors.append(f"{field} must be an integer")
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{field} must be an integer")
        return 0


__all__ = [
    "EVENT_GROUPS",
    "GENESIS_CHAIN_HASH",
    "LEDGER_EXPORT_REQUESTED",
    "SCHEMA_VERSION",
    "LedgerExportValidationError",
    "chain_hash_for",
    "event_group",
    "event_hash_for",
    "normalize_event_groups",
    "verify_ledger_export",
]
