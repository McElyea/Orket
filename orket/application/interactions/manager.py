"""Application authority for captured interaction admission, transitions and close."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.interaction_cancellation import InteractionCancellation
from orket.core.contracts.interaction_stream import CommitHandle, CommitIntent, StreamEventType, validate_interaction_id
from orket.streaming.bus import StreamBus

from .cancellation import _target, cancel_interaction
from .commit import CommitOrchestrator
from .context import InteractionContext
from .finalization import finalize_turn
from .queries import InteractionQueries
from .state import InteractionSessionState, InteractionState, admit_turn
from .streams import InteractionStreams

SessionLifecycleHook = Callable[[str], Awaitable[None]]


class InteractionManager:
    def __init__(self, *, bus: StreamBus, commit_orchestrator: CommitOrchestrator, project_root: Path,
                 stream_enabled: bool = False, inputs: RuntimeInputService | None = None,
                 on_session_started: SessionLifecycleHook | None = None,
                 on_session_closed: SessionLifecycleHook | None = None) -> None:
        if not project_root.is_absolute() or project_root != commit_orchestrator.store.project_root:
            raise ValueError("E_INTERACTION_ROOT_MISMATCH")
        self.bus, self.commit_orchestrator = bus, commit_orchestrator
        self._inputs, self._enabled = inputs or RuntimeInputService(), bool(stream_enabled)
        self._state = InteractionState()
        self.queries, self.streams = InteractionQueries(self._state), InteractionStreams(bus)
        self._on_session_started, self._on_session_closed = on_session_started, on_session_closed
        self._closing = False

    def stream_enabled(self) -> bool:
        return self._enabled

    async def start(self, session_params: dict[str, Any] | None = None) -> str:
        params = deepcopy(session_params or {})
        json.dumps(params)
        session_id = validate_interaction_id(self._inputs.create_effect_owner_id())
        timestamp = self._inputs.utc_now_iso()
        if self._closing:
            raise ValueError("Interaction manager is closing")
        admitted = False

        async def operation():
            nonlocal admitted
            async with self._state.lock:
                if self._closing or session_id in self._state.sessions:
                    raise ValueError("E_INTERACTION_SESSION_ADMISSION")
                self._state.sessions[session_id] = InteractionSessionState(session_id, params, timestamp, timestamp)
                admitted = True
            async with self._state.sessions[session_id].transition:
                if self._on_session_started is not None:
                    await self._on_session_started(session_id)
            return session_id

        try:
            return await run_owned_io(operation, label="interaction-start", preserve_failure=True)
        except (asyncio.CancelledError, OSError, RuntimeError, ValueError, TypeError):
            if admitted and session_id in self._state.sessions:
                await self.close(session_id)
            raise

    async def begin_turn(self, session_id: str, input_payload: dict[str, Any] | None = None,
                         turn_params: dict[str, Any] | None = None, *,
                         context_inputs: dict[str, Any] | None = None) -> str:
        payload, params, context = deepcopy(input_payload or {}), deepcopy(turn_params or {}), deepcopy(context_inputs or {})
        json.dumps([payload, params, context])
        budget = _stream_budget(context.get("workload_id", ""), params)
        timestamp, turn_id = self._inputs.utc_now_iso(), validate_interaction_id(self._inputs.create_effect_owner_id())
        session = self._state.session(session_id)
        admitted = False

        async def operation():
            nonlocal admitted
            async with self._state.lock:
                admit_turn(self._state, session, turn_id=turn_id, accepted_at=timestamp, context_inputs=context)
                admitted = True
            return await self._publish_admission(session, turn_id, payload, params, budget)

        async with session.transition:
            self._state.session(session_id)
            try:
                return await run_owned_io(operation, label="interaction-admission", preserve_failure=True)
            except (asyncio.CancelledError, OSError, RuntimeError, ValueError, TypeError):
                if admitted:
                    await self._abandon(session, turn_id, "admission_interrupted")
                raise

    async def _publish_admission(self, session, turn_id, payload, params, budget):
        if budget is not None:
            await self.bus.configure_turn_budget(session_id=session.session_id, turn_id=turn_id,
                                                 best_effort_max_events_per_turn=budget)
        await self.bus.publish(session_id=session.session_id, turn_id=turn_id, event_type=StreamEventType.TURN_ACCEPTED,
                                payload={"authoritative": False, "input": payload, "turn_params": params})
        return turn_id

    async def finalize(self, session_id: str, turn_id: str, *, require_workload_result: bool = False) -> CommitHandle:
        timestamp, mono = self._inputs.utc_now_iso(), self._inputs.monotonic_ns() // 1_000_000
        session = self._state.session(session_id)
        async with session.transition:
            self._state.session(session_id)
            turn = self._state.turn(session_id, turn_id)
            if require_workload_result and turn.workload is not None and turn.finalization is None:
                raise ValueError("Interaction workload has not published its result")
            return await finalize_turn(self, session_id, turn_id, timestamp, mono)

    def adopt_workload(self, session_id: str, turn_id: str, launch: Callable[[], asyncio.Task[Any]]) -> None:
        """Transfer dispatch synchronously to the application lifetime before returning admission."""
        session, turn = self._state.session(session_id), self._state.turn(session_id, turn_id)
        if session.closing or turn.finalization is not None or turn.workload is not None:
            raise ValueError("E_INTERACTION_DISPATCH_CLOSED")
        turn.workload = launch()

    async def cancel(self, target_id: str, *, session_id: str | None = None, session_target: bool = False,
                     timestamp: str | None = None) -> InteractionCancellation:
        captured = self._inputs.utc_now_iso() if timestamp is None else timestamp

        async def operation():
            async with self._state.lock:
                selected = _target(target_id, session_id, session_target, self._state.sessions, self._state.turns)
                if selected is not None and selected[1] is not None:
                    turn = self._state.turns.get(selected)
                    if turn is not None and turn.terminal_event is not None:
                        return InteractionCancellation("terminal", selected[0], selected[1], turn.finalized_at)
            if selected is None:
                return InteractionCancellation("not_found", session_id, None, None)
            session = self._state.sessions.get(selected[0])
            if session is None:
                return InteractionCancellation("not_found", session_id, None, None)
            async with session.transition:
                return await self._cancel(target_id, session_id, session_target, captured)

        return await run_owned_io(operation, label="interaction-state-cancellation", preserve_failure=True)

    async def _cancel(self, target_id, session_id, session_target, timestamp):
        return await cancel_interaction(target_id=target_id, expected_session_id=session_id, session_target=session_target,
                                        timestamp=timestamp, sessions=self._state.sessions, turns=self._state.turns,
                                        lock=self._state.lock, bus=self.bus)

    async def _abandon(self, session, turn_id, reason):
        timestamp, mono = self._inputs.utc_now_iso(), self._inputs.monotonic_ns() // 1_000_000

        async def operation():
            async with self._state.lock:
                turn = self._state.turn(session.session_id, turn_id)
                if turn.finalization is None:
                    self._state.intents[(session.session_id, turn_id)].append(
                        CommitIntent(type="decision", ref=f"fail_closed:{reason}"))
            if turn.finalization is None:
                await self._cancel(turn_id, session.session_id, False, timestamp)
            await finalize_turn(self, session.session_id, turn_id, timestamp, mono)

        await run_owned_io(operation, label="interaction-abandoned-admission", preserve_failure=True)

    async def create_context(self, session_id: str, turn_id: str) -> InteractionContext:
        async with self._state.lock:
            session, turn = self._state.session(session_id), self._state.turn(session_id, turn_id)
            params, envelope, lineage = deepcopy(session.params), deepcopy(turn.context_envelope), deepcopy(turn.provider_lineage)

        async def sink(intent):
            async with self._state.lock:
                self._state.session(session_id)
                if self._state.turn(session_id, turn_id).finalization is not None:
                    raise ValueError("E_INTERACTION_COMMIT_INPUTS_CLOSED")
                self._state.intents[(session_id, turn_id)].append(intent)

        async def emit(event_type, payload):
            if event_type in {StreamEventType.TURN_ACCEPTED, StreamEventType.TURN_INTERRUPTED,
                              StreamEventType.TURN_FINAL, StreamEventType.COMMIT_FINAL}:
                raise ValueError("E_INTERACTION_LIFECYCLE_EVENT_RESERVED")
            if payload.get("authoritative") is True:
                raise ValueError("E_INTERACTION_WORKLOAD_AUTHORITY_FORBIDDEN")
            payload["authoritative"] = False
            async with session.transition:
                self._state.session(session_id)
                if turn.canceled.is_set():
                    return False
                if turn.terminal_event is not None:
                    raise ValueError("Post-terminal events are forbidden except commit_final")
                event = await run_owned_io(lambda: self.bus.publish(session_id=session_id, turn_id=turn_id,
                                                                   event_type=event_type, payload=payload),
                                          label="interaction-event", preserve_failure=True)
                return event is not None

        return InteractionContext(session_id=session_id, turn_id=turn_id, session_params=params,
                                  packet1_context_envelope=envelope, packet1_provider_lineage=lineage,
                                  emit=emit, cancel_event=turn.canceled, commit_sink=sink)

    async def abort(self, session_id: str, turn_id: str, *, reason: str) -> None:
        session = self._state.session(session_id)
        async with session.transition:
            self._state.session(session_id)
            await self._abandon(session, turn_id, str(reason))

    async def close(self, session_id: str) -> None:
        session = self._state.session(session_id)
        if any(turn.workload is not None and not turn.workload.done()
               for (sid, _), turn in self._state.turns.items() if sid == session_id):
            raise ValueError("Drain the owning application workload before closing its interaction session")
        session.closing = True

        async def operation():
            async with session.transition:
                if session.closed:
                    return
                if session.active_turn_id is not None:
                    await self._abandon(session, session.active_turn_id, "session_closed")
                if self._on_session_closed is not None:
                    await self._on_session_closed(session_id)
                async with self._state.lock:
                    keys = [key for key in self._state.turns if key[0] == session_id]
                    for key in keys:
                        self._state.turns.pop(key)
                        self._state.intents.pop(key, None)
                    session.closed = True
                    self._state.sessions.pop(session_id, None)
                for _, turn_id in keys:
                    await self.bus.purge_turn(session_id, turn_id, drain_subscriber_queues=False)

        await run_owned_io(operation, label="interaction-close", preserve_failure=True)

    async def aclose(self) -> None:
        self._closing = True

        async def operation():
            results = await asyncio.gather(*(self.close(sid) for sid in tuple(self._state.sessions)), return_exceptions=True)
            errors = [value for value in results if isinstance(value, BaseException)]
            if errors:
                raise RuntimeError(f"Interaction teardown failed for {len(errors)} session(s)") from errors[0]

        await run_owned_io(operation, label="interaction-shutdown", preserve_failure=True)


def _stream_budget(workload_id: str, params: dict[str, Any]) -> int | None:
    raw = params.get("stream_budget")
    if raw is not None:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid stream_budget; expected a positive integer.") from exc
    return 2048 if str(workload_id).strip() == "model_stream_v1" else None
