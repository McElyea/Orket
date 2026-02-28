from __future__ import annotations

import time
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class StreamEventType(str, Enum):
    TURN_ACCEPTED = "turn_accepted"
    MODEL_SELECTED = "model_selected"
    MODEL_LOADING = "model_loading"
    MODEL_READY = "model_ready"
    TOKEN_DELTA = "token_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_RESULT = "tool_call_result"
    TURN_INTERRUPTED = "turn_interrupted"
    TURN_FINAL = "turn_final"
    COMMIT_FINAL = "commit_final"


class DropRange(BaseModel):
    start_seq: int
    end_seq: int

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_seq > self.end_seq:
            raise ValueError("start_seq must be <= end_seq")
        return self


class StreamEvent(BaseModel):
    schema_v: Literal["1.0"] = "1.0"
    session_id: str
    turn_id: str
    seq: int
    mono_ts_ms: int
    event_type: StreamEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    wall_ts: str | int | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        ranges = self.payload.get("dropped_seq_ranges")
        if ranges is None:
            return self
        parsed = [DropRange.model_validate(item) for item in ranges]
        for i in range(1, len(parsed)):
            prev = parsed[i - 1]
            cur = parsed[i]
            if cur.start_seq <= prev.end_seq:
                raise ValueError("dropped_seq_ranges must be non-overlapping and ascending")
        return self


class CommitIntent(BaseModel):
    type: Literal["tool_result", "decision", "turn_finalize"]
    ref: str
    payload_digest: str | None = None


class CommitHandle(BaseModel):
    session_id: str
    turn_id: str
    status: Literal["pending"] = "pending"
    requested_at_mono_ts_ms: int


class EventClass(str, Enum):
    MUST_DELIVER = "must_deliver"
    BEST_EFFORT = "best_effort"
    BOUNDED = "bounded"


MUST_DELIVER_EVENTS: set[StreamEventType] = {
    StreamEventType.TURN_ACCEPTED,
    StreamEventType.TURN_INTERRUPTED,
    StreamEventType.TURN_FINAL,
    StreamEventType.COMMIT_FINAL,
}

BEST_EFFORT_EVENTS: set[StreamEventType] = {
    StreamEventType.TOKEN_DELTA,
    StreamEventType.MODEL_LOADING,
    StreamEventType.MODEL_SELECTED,
    StreamEventType.MODEL_READY,
}

BOUNDED_EVENTS: set[StreamEventType] = {
    StreamEventType.TOOL_CALL_STARTED,
    StreamEventType.TOOL_CALL_RESULT,
}


def event_class(event_type: StreamEventType) -> EventClass:
    if event_type in MUST_DELIVER_EVENTS:
        return EventClass.MUST_DELIVER
    if event_type in BEST_EFFORT_EVENTS:
        return EventClass.BEST_EFFORT
    return EventClass.BOUNDED


def mono_ts_ms_now() -> int:
    return int(time.monotonic_ns() / 1_000_000)


def wall_ts_now_iso() -> str:
    return datetime.now(UTC).isoformat()
