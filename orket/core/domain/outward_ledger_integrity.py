from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from orket.core.domain.outward_ledger import GENESIS_CHAIN_HASH, event_hash_for
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord

ANCHOR_SCHEMA = "outward_ledger_anchor.v2"
COMMITMENT_SCHEMA = "outward_ledger_append.v2"


class OutwardLedgerIntegrityError(ValueError):
    def __init__(self, message: str, *, category: str = "integrity") -> None:
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class LedgerAnchor:
    run_id: str
    event_count: int = 0
    chain_hash: str = GENESIS_CHAIN_HASH
    origin_ref: str = "native"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ANCHOR_SCHEMA, "run_id": self.run_id,
            "event_count": self.event_count, "chain_hash": self.chain_hash, "origin_ref": self.origin_ref,
        }

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> LedgerAnchor:
        fields = {"schema_version", "run_id", "event_count", "chain_hash", "origin_ref"}
        if set(value) != fields or value["schema_version"] != ANCHOR_SCHEMA:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_ANCHOR_SCHEMA")
        count, digest, run_id, origin = (value[key] for key in ("event_count", "chain_hash", "run_id", "origin_ref"))
        if type(count) is not int or count < 0 or not isinstance(run_id, str) or not run_id.strip():
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_ANCHOR_IDENTITY")
        if not isinstance(origin, str) or (origin != "native" and not re.fullmatch(r"legacy:[0-9a-f]{64}", origin)):
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_ANCHOR_ORIGIN")
        if not isinstance(digest, str) or (digest != GENESIS_CHAIN_HASH if count == 0 else not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_ANCHOR_HASH")
        return cls(run_id, count, digest, origin)


def append_chain_hash(event: LedgerEvent, sequence: int, previous: str, origin_ref: str) -> str:
    # Bind original v1 cells too: migration may retain absent hashes or a v1 chain.
    payload = {
        "schema_version": COMMITMENT_SCHEMA, "run_id": event.run_id,
        "append_sequence": sequence, "previous_chain_hash": previous, "origin_ref": origin_ref,
        "event_hash": event_hash_for(event),
        "stored_event_hash": event.event_hash, "stored_chain_hash": event.chain_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RetainedLedgerSnapshot:
    run: OutwardRunRecord
    events: tuple[LedgerEvent, ...]
    anchor: LedgerAnchor
    independent_count: int
    prefix_hashes: tuple[str, ...]

    def compare_anchor(self, value: Mapping[str, Any]) -> None:
        previous = LedgerAnchor.parse(value)
        if previous.run_id != self.run.run_id or previous.origin_ref != self.anchor.origin_ref:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_EXTERNAL_ANCHOR_SCOPE")
        if previous.event_count > self.anchor.event_count:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_EXTERNAL_ANCHOR_FUTURE")
        digest = self.prefix_hashes[previous.event_count - 1] if previous.event_count else GENESIS_CHAIN_HASH
        if digest != previous.chain_hash:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_EXTERNAL_ANCHOR_MISMATCH")
