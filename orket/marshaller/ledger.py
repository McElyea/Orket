from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots

from .canonical import hash_canonical_json


class LedgerWriter:
    """Append-only JSONL ledger with tamper-evident hash chaining."""

    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path, = capture_file_roots([ledger_path])
        self._event_seq = 0
        self._prev_digest = ""

    @property
    def current_digest(self) -> str:
        return self._prev_digest

    @classmethod
    async def resume(cls, ledger_path: Path) -> LedgerWriter:
        writer = cls(ledger_path)
        ledger_path = writer.ledger_path
        if not await run_owned_thread(ledger_path.exists, label="marshaller-ledger-exists"):
            return writer
        last_record = await run_owned_thread(partial(_last_record, ledger_path), label="marshaller-ledger-read")
        if not last_record:
            return writer
        writer._event_seq = int(last_record.get("event_seq", 0))
        writer._prev_digest = str(last_record.get("entry_digest", ""))
        return writer

    async def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._event_seq += 1
        record: dict[str, Any] = {
            "event_seq": self._event_seq,
            "event_type": event_type,
            "prev_entry_digest": self._prev_digest,
            "payload": payload,
        }
        record["entry_digest"] = hash_canonical_json(record)
        path, = capture_file_roots([self.ledger_path])
        line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        # Return the detached JSON value actually published, not a borrowed payload.
        record = json.loads(line)

        async def publish() -> dict[str, Any]:
            await self._append_json_line(path, line)
            self._prev_digest = str(record["entry_digest"])
            return record

        return await run_owned_io(publish, label="marshaller-ledger-publication", preserve_failure=True)

    async def _append_json_line(self, path: Path, line: str) -> None:
        await run_owned_thread(partial(path.parent.mkdir, parents=True, exist_ok=True), label="marshaller-ledger-parent")
        await run_owned_thread(partial(_append_text, path, line), label="marshaller-ledger-append")


def _append_text(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _last_record(path: Path) -> dict[str, Any] | None:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    payload = json.loads(lines[-1])
    if not isinstance(payload, dict):
        return None
    return payload
