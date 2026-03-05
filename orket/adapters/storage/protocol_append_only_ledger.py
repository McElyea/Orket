from __future__ import annotations

import json
import os
from pathlib import Path
import struct
from typing import Any

from orket.application.workflows.protocol_hashing import canonical_json


MAX_LEDGER_PAYLOAD_BYTES = 4 * 1024 * 1024


class LedgerFramingError(ValueError):
    """Deterministic append-only ledger framing/replay error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = str(code).strip() or "E_LEDGER"
        self.detail = str(detail).strip()
        super().__init__(f"{self.code}:{self.detail}" if self.detail else self.code)


def _build_crc32c_table() -> list[int]:
    polynomial = 0x82F63B78  # Castagnoli, reversed form for byte-wise update.
    table: list[int] = []
    for value in range(256):
        crc = value
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ polynomial
            else:
                crc >>= 1
        table.append(crc & 0xFFFFFFFF)
    return table


_CRC32C_TABLE = _build_crc32c_table()


def crc32c(payload: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in payload:
        crc = _CRC32C_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def encode_lpj_c32_record(
    payload: dict[str, Any],
    *,
    max_payload_bytes: int = MAX_LEDGER_PAYLOAD_BYTES,
) -> bytes:
    payload_bytes = canonical_json(payload).encode("utf-8")
    payload_len = len(payload_bytes)
    if payload_len > max_payload_bytes:
        raise LedgerFramingError(
            "E_LEDGER_RECORD_TOO_LARGE",
            f"{payload_len}>{max_payload_bytes}",
        )
    checksum = crc32c(payload_bytes)
    return struct.pack(">I", payload_len) + payload_bytes + struct.pack(">I", checksum)


def decode_lpj_c32_stream(
    data: bytes,
    *,
    max_payload_bytes: int = MAX_LEDGER_PAYLOAD_BYTES,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    total_len = len(data)
    last_event_seq = 0

    while True:
        if offset + 4 > total_len:
            break
        payload_len = struct.unpack(">I", data[offset : offset + 4])[0]
        if payload_len > max_payload_bytes:
            raise LedgerFramingError("E_LEDGER_RECORD_TOO_LARGE", f"{payload_len}>{max_payload_bytes}")
        record_end = offset + 4 + payload_len + 4
        if record_end > total_len:
            # Partial tail: end-of-log by contract.
            break

        payload_bytes = data[offset + 4 : offset + 4 + payload_len]
        expected_crc = struct.unpack(">I", data[offset + 4 + payload_len : record_end])[0]
        actual_crc = crc32c(payload_bytes)
        if expected_crc != actual_crc:
            raise LedgerFramingError("E_LEDGER_CORRUPT", f"offset={offset}")

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LedgerFramingError("E_LEDGER_PARSE", f"offset={offset}") from exc
        if not isinstance(payload, dict):
            raise LedgerFramingError("E_LEDGER_PARSE", f"offset={offset}:record_not_object")

        event_seq = payload.get("event_seq")
        if not isinstance(event_seq, int) or event_seq <= 0:
            raise LedgerFramingError("E_LEDGER_SEQ", f"offset={offset}:missing_event_seq")
        if event_seq <= last_event_seq:
            raise LedgerFramingError("E_LEDGER_SEQ", f"offset={offset}:non_monotonic")
        last_event_seq = event_seq
        records.append(payload)
        offset = record_end

    return records


class AppendOnlyRunLedger:
    """Append-only LPJ-C32 v1 run ledger."""

    def __init__(self, path: Path, *, max_payload_bytes: int = MAX_LEDGER_PAYLOAD_BYTES) -> None:
        self.path = path
        self.max_payload_bytes = int(max_payload_bytes)
        self._next_event_seq: int | None = None

    def append_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = dict(payload or {})
        next_event_seq = self.next_event_seq()
        explicit_event_seq = event.get("event_seq")
        if explicit_event_seq is None:
            event["event_seq"] = next_event_seq
        elif int(explicit_event_seq) != next_event_seq:
            raise LedgerFramingError("E_LEDGER_SEQ", f"expected={next_event_seq},actual={explicit_event_seq}")

        frame = encode_lpj_c32_record(event, max_payload_bytes=self.max_payload_bytes)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(frame)
            handle.flush()
            os.fsync(handle.fileno())
        self._next_event_seq = int(event["event_seq"]) + 1
        return event

    def replay_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            self._next_event_seq = 1
            return []
        payload = self.path.read_bytes()
        events = decode_lpj_c32_stream(payload, max_payload_bytes=self.max_payload_bytes)
        if events:
            self._next_event_seq = int(events[-1]["event_seq"]) + 1
        else:
            self._next_event_seq = 1
        return events

    def next_event_seq(self) -> int:
        if self._next_event_seq is None:
            _ = self.replay_events()
        return int(self._next_event_seq or 1)
