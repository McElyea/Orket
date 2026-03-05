from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .canonical import hash_canonical_json


class LedgerWriter:
    """Append-only JSONL ledger with tamper-evident hash chaining."""

    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = ledger_path
        self._event_seq = 0
        self._prev_digest = ""

    @property
    def current_digest(self) -> str:
        return self._prev_digest

    async def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._event_seq += 1
        record: dict[str, Any] = {
            "event_seq": self._event_seq,
            "event_type": event_type,
            "prev_entry_digest": self._prev_digest,
            "payload": payload,
        }
        record["entry_digest"] = hash_canonical_json(record)
        await self._append_json_line(record)
        self._prev_digest = str(record["entry_digest"])
        return record

    async def _append_json_line(self, payload: dict[str, Any]) -> None:
        await asyncio.to_thread(self.ledger_path.parent.mkdir, parents=True, exist_ok=True)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        await asyncio.to_thread(_append_text, self.ledger_path, line)


def _append_text(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

