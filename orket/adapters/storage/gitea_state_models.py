from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


SNAPSHOT_MARKER = "<!-- ORKET_SNAPSHOT_V1 -->"
EVENT_MARKER = "[ORKET_EVENT_V1]"


class LeaseInfo(BaseModel):
    owner_id: Optional[str] = None
    acquired_at: Optional[str] = None
    expires_at: Optional[str] = None
    epoch: int = 0


class CardSnapshot(BaseModel):
    card_id: str
    state: str
    backend: str = "gitea"
    version: int = 1
    lease: LeaseInfo = Field(default_factory=LeaseInfo)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StateEvent(BaseModel):
    event_type: str
    created_at: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def encode_snapshot(snapshot: CardSnapshot) -> str:
    """
    Compact, canonical issue-body payload for gitea card state.
    """
    payload = snapshot.model_dump(exclude_none=True)
    return f"{SNAPSHOT_MARKER}\n{json.dumps(payload, separators=(',', ':'), sort_keys=True)}"


def decode_snapshot(body: str) -> CardSnapshot:
    marker_index = body.find(SNAPSHOT_MARKER)
    if marker_index < 0:
        raise ValueError("Missing ORKET snapshot marker in issue body.")
    json_blob = body[marker_index + len(SNAPSHOT_MARKER) :].strip()
    if not json_blob:
        raise ValueError("Missing snapshot payload in issue body.")
    data = json.loads(json_blob)
    if not isinstance(data, dict):
        raise ValueError("Snapshot payload must be a JSON object.")
    return CardSnapshot.model_validate(data)


def build_event_comment(
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    idempotency_key: Optional[str] = None,
    created_at: Optional[str] = None,
) -> str:
    event = StateEvent(
        event_type=event_type,
        created_at=created_at or _utc_now_iso(),
        payload=payload or {},
        idempotency_key=idempotency_key,
    )
    serialized = json.dumps(event.model_dump(exclude_none=True), separators=(",", ":"), sort_keys=True)
    return f"{EVENT_MARKER} {serialized}"


def parse_event_comment(comment: str) -> StateEvent:
    if not comment.startswith(EVENT_MARKER):
        raise ValueError("Comment is not an ORKET event.")
    blob = comment[len(EVENT_MARKER) :].strip()
    data = json.loads(blob)
    if not isinstance(data, dict):
        raise ValueError("Event payload must be a JSON object.")
    return StateEvent.model_validate(data)
