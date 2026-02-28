from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import StreamEvent, StreamEventType


class StreamLawViolation(Exception):
    pass


@dataclass
class TurnLawState:
    last_seq: int | None = None
    seen_seqs: set[int] = field(default_factory=set)
    terminal_event: StreamEventType | None = None
    terminal_seq: int | None = None
    seen_commit_final: bool = False
    last_mono_ts_ms: int | None = None


class StreamLawChecker:
    """
    Subscriber-side law checker for stream event invariants.
    """

    def __init__(self):
        self._turns: dict[tuple[str, str], TurnLawState] = {}

    def consume(self, raw_event: dict[str, Any]) -> None:
        event = StreamEvent.model_validate(raw_event)
        key = (event.session_id, event.turn_id)
        state = self._turns.setdefault(key, TurnLawState())

        if event.seq in state.seen_seqs:
            raise StreamLawViolation(f"R0 seq duplicate at seq={event.seq}")
        state.seen_seqs.add(event.seq)

        if state.last_seq is not None and event.seq <= state.last_seq:
            raise StreamLawViolation(
                f"R0 seq non-increasing: prev={state.last_seq} current={event.seq}"
            )

        if state.last_seq is not None and event.seq > (state.last_seq + 1):
            self._validate_gap_with_dropped_ranges(event, expected_start=state.last_seq + 1, expected_end=event.seq - 1)

        if state.last_mono_ts_ms is not None and event.mono_ts_ms < state.last_mono_ts_ms:
            raise StreamLawViolation(
                f"R0 mono_ts_ms decreased: prev={state.last_mono_ts_ms} current={event.mono_ts_ms}"
            )

        if state.terminal_event is not None:
            if event.event_type != StreamEventType.COMMIT_FINAL:
                raise StreamLawViolation(
                    f"R3 post-terminal event forbidden: terminal={state.terminal_event.value} got={event.event_type.value}"
                )
            if state.seen_commit_final:
                raise StreamLawViolation("R1b duplicate commit_final for turn")

        if event.event_type in {StreamEventType.TURN_INTERRUPTED, StreamEventType.TURN_FINAL}:
            if state.terminal_event is not None:
                raise StreamLawViolation("R3 terminal event exclusivity violated")
            state.terminal_event = event.event_type
            state.terminal_seq = event.seq

        if event.event_type == StreamEventType.COMMIT_FINAL:
            state.seen_commit_final = True
            self._validate_commit_final(event, state)

        state.last_seq = event.seq
        state.last_mono_ts_ms = event.mono_ts_ms

    def _validate_gap_with_dropped_ranges(self, event: StreamEvent, *, expected_start: int, expected_end: int) -> None:
        ranges = event.payload.get("dropped_seq_ranges")
        if not isinstance(ranges, list) or not ranges:
            raise StreamLawViolation(
                f"R9b seq gap without dropped_seq_ranges: missing={expected_start}..{expected_end}"
            )
        normalized: list[tuple[int, int]] = []
        for item in ranges:
            if not isinstance(item, dict):
                raise StreamLawViolation("R0 dropped_seq_ranges entries must be objects")
            start = int(item.get("start_seq"))
            end = int(item.get("end_seq"))
            if start > end:
                raise StreamLawViolation("R0 dropped_seq_ranges start_seq must be <= end_seq")
            normalized.append((start, end))
        normalized.sort()
        cursor = expected_start
        for start, end in normalized:
            if start > cursor:
                raise StreamLawViolation(
                    f"R0 dropped_seq_ranges missing coverage for seq={cursor}"
                )
            if end < cursor:
                continue
            cursor = end + 1
            if cursor > expected_end:
                break
        if cursor <= expected_end:
            raise StreamLawViolation(
                f"R0 dropped_seq_ranges incomplete coverage; first_uncovered={cursor}"
            )

    def _validate_commit_final(self, event: StreamEvent, state: TurnLawState) -> None:
        payload = event.payload
        required = ["authoritative", "commit_digest", "commit_outcome", "issues", "artifact_refs"]
        for key in required:
            if key not in payload:
                raise StreamLawViolation(f"R1b commit_final missing required field '{key}'")
        if payload.get("authoritative") is not True:
            raise StreamLawViolation("R1b commit_final.authoritative must be true")
        if payload.get("commit_outcome") not in {"ok", "fail_closed"}:
            raise StreamLawViolation("R1b commit_final.commit_outcome invalid")
        if state.terminal_seq is None:
            raise StreamLawViolation("R1b commit_final arrived before terminal turn event")
        if event.seq <= state.terminal_seq:
            raise StreamLawViolation(
                f"R1b commit_final seq must be > terminal seq ({state.terminal_seq})"
            )
