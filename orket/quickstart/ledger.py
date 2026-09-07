from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiofiles

REQUIRED_EVENT_FIELDS = (
    "run_id",
    "sequence",
    "event_type",
    "timestamp_utc",
    "payload",
    "previous_event_hash",
    "event_hash",
)


@dataclass(frozen=True)
class LedgerVerificationResult:
    valid: bool
    event_count: int
    run_id: str | None
    final_event_hash: str | None
    errors: tuple[str, ...]


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_event_hash(event: Mapping[str, Any]) -> str:
    hash_payload = dict(event)
    hash_payload.pop("event_hash", None)
    return hashlib.sha256(canonical_json(hash_payload).encode("utf-8")).hexdigest()


def build_event(
    *,
    run_id: str,
    sequence: int,
    event_type: str,
    timestamp_utc: str,
    payload: Mapping[str, Any],
    previous_event_hash: str | None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "run_id": run_id,
        "sequence": sequence,
        "event_type": event_type,
        "timestamp_utc": timestamp_utc,
        "payload": dict(payload),
        "previous_event_hash": previous_event_hash,
    }
    event["event_hash"] = compute_event_hash(event)
    return event


class QuickstartLedgerWriter:
    def __init__(
        self,
        *,
        path: Path,
        run_id: str,
        timestamp_factory: Callable[[], str],
        sequence_start: int = 1,
    ) -> None:
        if sequence_start not in {0, 1}:
            raise ValueError("sequence_start must be 0 or 1")
        self.path = path
        self.run_id = run_id
        self._timestamp_factory = timestamp_factory
        self._next_sequence = sequence_start
        self._previous_event_hash: str | None = None

    @classmethod
    async def create(
        cls,
        *,
        path: Path,
        run_id: str,
        timestamp_factory: Callable[[], str],
        sequence_start: int = 1,
    ) -> QuickstartLedgerWriter:
        await _mkdir(path.parent)
        async with aiofiles.open(path, "w", encoding="utf-8") as ledger_file:
            await ledger_file.write("")
        return cls(
            path=path,
            run_id=run_id,
            timestamp_factory=timestamp_factory,
            sequence_start=sequence_start,
        )

    async def emit(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = build_event(
            run_id=self.run_id,
            sequence=self._next_sequence,
            event_type=event_type,
            timestamp_utc=self._timestamp_factory(),
            payload=payload,
            previous_event_hash=self._previous_event_hash,
        )
        async with aiofiles.open(self.path, "a", encoding="utf-8") as ledger_file:
            await ledger_file.write(canonical_json(event) + "\n")
        self._previous_event_hash = str(event["event_hash"])
        self._next_sequence += 1
        return event


async def load_ledger_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with aiofiles.open(path, encoding="utf-8") as ledger_file:
        line_number = 0
        async for raw_line in ledger_file:
            line_number += 1
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"ledger line {line_number} is not valid JSON: {exc.msg}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"ledger line {line_number} must be a JSON object")
            events.append(payload)
    return events


async def verify_ledger_file(path: Path) -> LedgerVerificationResult:
    try:
        events = await load_ledger_events(path)
    except (OSError, ValueError) as exc:
        return LedgerVerificationResult(
            valid=False,
            event_count=0,
            run_id=None,
            final_event_hash=None,
            errors=(str(exc),),
        )
    return verify_ledger_events(events)


def verify_ledger_events(events: list[Mapping[str, Any]]) -> LedgerVerificationResult:
    errors: list[str] = []
    if not events:
        errors.append("ledger must contain at least one event")
        return LedgerVerificationResult(False, 0, None, None, tuple(errors))

    run_id: str | None = None
    expected_sequence: int | None = None
    previous_event_hash: str | None = None
    final_event_hash: str | None = None

    for index, event in enumerate(events):
        prefix = f"event[{index}]"
        _validate_required_fields(prefix, event, errors)

        sequence = _sequence_value(prefix, event.get("sequence"), errors)
        if index == 0:
            if sequence not in {0, 1}:
                errors.append(f"{prefix}.sequence must start at 0 or 1")
            expected_sequence = sequence
            if event.get("previous_event_hash") is not None:
                errors.append(f"{prefix}.previous_event_hash must be null for the first event")
        elif expected_sequence is not None:
            expected_sequence += 1
            if sequence != expected_sequence:
                errors.append(f"{prefix}.sequence must be {expected_sequence}")
            if event.get("previous_event_hash") != previous_event_hash:
                errors.append(f"{prefix}.previous_event_hash must equal the prior event_hash")

        event_run_id = event.get("run_id")
        if not isinstance(event_run_id, str) or not event_run_id.strip():
            errors.append(f"{prefix}.run_id must be a non-empty string")
        elif run_id is None:
            run_id = event_run_id
        elif event_run_id != run_id:
            errors.append(f"{prefix}.run_id must match the first event run_id")

        if not isinstance(event.get("event_type"), str) or not str(event.get("event_type") or "").strip():
            errors.append(f"{prefix}.event_type must be a non-empty string")
        if not isinstance(event.get("timestamp_utc"), str) or not str(event.get("timestamp_utc") or "").strip():
            errors.append(f"{prefix}.timestamp_utc must be a non-empty string")
        if not isinstance(event.get("payload"), dict):
            errors.append(f"{prefix}.payload must be a JSON object")

        expected_hash = compute_event_hash(event)
        observed_hash = event.get("event_hash")
        if not isinstance(observed_hash, str) or not observed_hash.strip():
            errors.append(f"{prefix}.event_hash must be a non-empty string")
        elif observed_hash != expected_hash:
            errors.append(f"{prefix}.event_hash mismatch")

        previous_event_hash = observed_hash if isinstance(observed_hash, str) else None
        final_event_hash = previous_event_hash

    return LedgerVerificationResult(
        valid=not errors,
        event_count=len(events),
        run_id=run_id,
        final_event_hash=final_event_hash,
        errors=tuple(errors),
    )


def _validate_required_fields(prefix: str, event: Mapping[str, Any], errors: list[str]) -> None:
    for field in REQUIRED_EVENT_FIELDS:
        if field not in event:
            errors.append(f"{prefix}.{field} is required")


def _sequence_value(prefix: str, value: Any, errors: list[str]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{prefix}.sequence must be an integer")
        return -1
    return value


async def _mkdir(path: Path) -> None:
    await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
