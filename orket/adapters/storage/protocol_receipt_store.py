"""Synchronous receipt files, used exclusively through the repository's owned worker."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from orket.core.contracts.protocol_error_codes import (
    E_RECEIPT_LOG_PARSE_PREFIX,
    E_RECEIPT_LOG_SCHEMA_PREFIX,
    E_RECEIPT_SEQ_INVALID_PREFIX,
    E_RECEIPT_SEQ_NON_MONOTONIC_PREFIX,
)
from orket.core.contracts.protocol_hashing import hash_canonical_json
from orket.core.contracts.tool_invocation_contracts import PROTOCOL_RECEIPT_SCHEMA_VERSION

side_effecting = True


class ProtocolReceiptStore:
    side_effecting = True

    def __init__(self, path: Path):
        self.path = path

    def append(
        self,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        receipts_path = self.path
        existing_rows = self.list()
        existing_by_digest = {
            str(row.get("receipt_digest") or ""): dict(row)
            for row in existing_rows
            if str(row.get("receipt_digest") or "").strip()
        }

        last_seq = 0
        for row in existing_rows:
            try:
                seq = int(row.get("receipt_seq") or 0)
            except (TypeError, ValueError):
                seq = 0
            if seq > last_seq:
                last_seq = seq

        normalized = dict(receipt or {})
        normalized["schema_version"] = str(normalized.get("schema_version") or PROTOCOL_RECEIPT_SCHEMA_VERSION)
        receipt_digest = str(normalized.get("receipt_digest") or "").strip()
        if not receipt_digest:
            digest_payload = dict(normalized)
            digest_payload.pop("receipt_digest", None)
            receipt_digest = hash_canonical_json(digest_payload)
            normalized["receipt_digest"] = receipt_digest

        if receipt_digest in existing_by_digest:
            return existing_by_digest[receipt_digest]

        raw_seq = normalized.get("receipt_seq")
        if raw_seq is None:
            normalized["receipt_seq"] = last_seq + 1
        else:
            try:
                normalized["receipt_seq"] = int(raw_seq)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{E_RECEIPT_SEQ_INVALID_PREFIX}:{raw_seq}") from exc
            if int(normalized["receipt_seq"]) <= last_seq:
                raise ValueError(f"{E_RECEIPT_SEQ_NON_MONOTONIC_PREFIX}:{normalized['receipt_seq']}<=last:{last_seq}")

        line = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        receipts_path.parent.mkdir(parents=True, exist_ok=True)
        with receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return normalized

    def list(self) -> list[dict[str, Any]]:
        receipts_path = self.path
        if not receipts_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with receipts_path.open("r", encoding="utf-8") as handle:
            for line_index, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{E_RECEIPT_LOG_PARSE_PREFIX}:line={line_index}") from exc
                if not isinstance(parsed, dict):
                    raise ValueError(f"{E_RECEIPT_LOG_SCHEMA_PREFIX}:line={line_index}")
                rows.append(dict(parsed))
        rows.sort(
            key=lambda row: (
                int(row.get("receipt_seq") or 0),
                str(row.get("receipt_digest") or ""),
            )
        )
        return rows
