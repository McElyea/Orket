"""One observed finalization attempt, retained for every waiter and retry."""
import asyncio
import logging

from orket.adapters.execution.owned_io import run_owned_io
from orket.core.contracts.interaction_stream import CommitHandle, CommitIntent, StreamEventType

from .state import turn_record

LOGGER = logging.getLogger(__name__)


async def finalize_turn(owner, session_id: str, turn_id: str, timestamp: str, monotonic_ms: int) -> CommitHandle:
    """Caller holds the session transition gate through observation and cleanup."""
    state = owner._state
    async with state.lock:
        turn = state.turn(session_id, turn_id)
        if turn.finalization is None:
            intents = tuple(state.intents[(session_id, turn_id)]) or (CommitIntent(type="turn_finalize", ref=turn_id),)
            turn.finalization = asyncio.create_task(
                _supervise(owner, session_id, turn_id, timestamp, monotonic_ms, intents),
                name=f"interaction-finalize:{session_id}:{turn_id}",
            )
        task = turn.finalization

    async def observe():
        return await task

    return await run_owned_io(observe, label="interaction-finalization", preserve_failure=True)


async def _supervise(owner, session_id, turn_id, timestamp, monotonic_ms, intents):
    try:
        return await _publish(owner, session_id, turn_id, timestamp, monotonic_ms, intents)
    except (Exception, asyncio.CancelledError) as exc:  # transition supervisor retains failure for every observer
        async with owner._state.lock:
            session = owner._state.session(session_id)
            session.failure = f"{type(exc).__name__}: {exc}"
            turn_record(session, turn_id)["commit_failure"] = session.failure
        LOGGER.error("Interaction finalization failed: session=%s turn=%s", session_id, turn_id, exc_info=True)
        raise


async def _publish(owner, session_id, turn_id, timestamp, monotonic_ms, intents):
    state = owner._state
    async with state.lock:
        session, turn = state.session(session_id), state.turn(session_id, turn_id)
        emit_terminal = turn.terminal_event is None
        if emit_terminal:
            turn.terminal_event, turn.finalized_at = StreamEventType.TURN_FINAL.value, timestamp
            turn_record(session, turn_id).update(terminal_event=turn.terminal_event, status="finalized", finalized_at=timestamp)
        session.updated_at = timestamp
    if emit_terminal:
        await owner.bus.publish(session_id=session_id, turn_id=turn_id, event_type=StreamEventType.TURN_FINAL,
                                payload={"authoritative": False})
    outcome = await owner.commit_orchestrator.commit(session_id=session_id, turn_id=turn_id, intents=list(intents))
    if outcome.get("authoritative") is not True:
        raise ValueError("E_INTERACTION_COMMIT_UNVERIFIED")
    await owner.commit_orchestrator.trace(session_id=session_id, turn_id=turn_id)
    await owner.bus.publish(session_id=session_id, turn_id=turn_id, event_type=StreamEventType.COMMIT_FINAL, payload=outcome)
    async with state.lock:
        if session.active_turn_id == turn_id:
            session.active_turn_id = None
        turn_record(session, turn_id).update(commit_outcome=outcome["commit_outcome"], commit_id=outcome["commit_id"],
                                             authoritative_commit=True)
    await owner.bus.purge_turn(session_id, turn_id, drain_subscriber_queues=False)
    return CommitHandle(session_id=session_id, turn_id=turn_id, requested_at_mono_ts_ms=monotonic_ms)
