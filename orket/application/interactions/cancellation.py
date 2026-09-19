"""Application-owned interaction cancellation transition."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from orket.core.contracts.interaction_cancellation import InteractionCancellation
from orket.core.contracts.interaction_stream import StreamEventType
from orket.streaming.bus import StreamBus


def _target(
    target_id: str, expected_session_id: str | None, session_target: bool, sessions: Mapping[str, Any],
    turns: Mapping[tuple[str, str], Any],
) -> tuple[str, str | None] | None:
    if expected_session_id is not None:
        session = sessions.get(expected_session_id)
        if session is None or session.closed:
            return None
        if session_target:
            return expected_session_id, session.active_turn_id
        if (expected_session_id, target_id) in turns:
            return expected_session_id, target_id
        return None
    if target_id in sessions:
        return target_id, sessions[target_id].active_turn_id
    return next(((sid, tid) for sid, tid in turns if tid == target_id), None)


async def cancel_interaction(
    *, target_id: str, expected_session_id: str | None, session_target: bool, timestamp: str,
    sessions: Mapping[str, Any], turns: Mapping[tuple[str, str], Any],
    lock: asyncio.Lock, bus: StreamBus,
) -> InteractionCancellation:
    async with lock:
        selected = _target(target_id, expected_session_id, session_target, sessions, turns)
        if selected is None:
            return InteractionCancellation("not_found", expected_session_id, None, None)
        session_id, turn_id = selected
        if turn_id is None:
            return InteractionCancellation("idle", session_id, None, None)
        turn = turns.get((session_id, turn_id))
        if turn is None:
            return InteractionCancellation("not_found", session_id, turn_id, None)
        if turn.terminal_event is not None:
            return InteractionCancellation("terminal", session_id, turn_id, turn.finalized_at)
        turn.canceled.set()
        turn.terminal_event = StreamEventType.TURN_INTERRUPTED.value
        turn.finalized_at = timestamp
        session = sessions.get(session_id)
        if session is not None:
            session.updated_at = timestamp
            record = next((row for row in session.turn_history if row.get("turn_id") == turn_id), None)
            if record is not None:
                record.update(terminal_event=turn.terminal_event, status="interrupted", finalized_at=timestamp)
    # Return a changed outcome only after both state transition and stream publication.
    await bus.publish(
        session_id=session_id, turn_id=turn_id, event_type=StreamEventType.TURN_INTERRUPTED,
        payload={"authoritative": False, "reason": "canceled"},
    )
    return InteractionCancellation("cancelled", session_id, turn_id, timestamp)
