from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .bus import StreamBus
from .contracts import CommitHandle, CommitIntent, StreamEventType, mono_ts_ms_now


@dataclass
class InteractionSessionState:
    session_id: str
    params: dict[str, Any]
    active_turn_id: str | None = None
    closed: bool = False


@dataclass
class TurnState:
    turn_id: str
    canceled: asyncio.Event
    terminal_event: str | None = None
    commit_started: bool = False


class InteractionContext:
    def __init__(
        self,
        *,
        session_id: str,
        turn_id: str,
        bus: StreamBus,
        cancel_event: asyncio.Event,
        commit_sink: Callable[[CommitIntent], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self.turn_id = turn_id
        self._bus = bus
        self._cancel_event = cancel_event
        self._commit_sink = commit_sink

    async def emit_event(self, event_type: StreamEventType, payload: dict[str, Any]) -> None:
        await self._bus.publish(
            session_id=self.session_id,
            turn_id=self.turn_id,
            event_type=event_type,
            payload=payload,
        )

    async def request_commit(self, intent: CommitIntent) -> None:
        await self._commit_sink(intent)

    def is_canceled(self) -> bool:
        return self._cancel_event.is_set()

    async def await_cancel(self) -> None:
        await self._cancel_event.wait()


class CommitOrchestrator:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()

    async def commit(self, *, session_id: str, turn_id: str, intents: list[CommitIntent]) -> dict[str, Any]:
        # Deterministic digest over commit inputs.
        payload = {
            "session_id": session_id,
            "turn_id": turn_id,
            "intents": [intent.model_dump() for intent in intents],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

        artifact_root = self.project_root / "workspace" / "interactions" / session_id / turn_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        authority_path = artifact_root / "authority_commit.json"
        authority_path.write_text(
            json.dumps(
                {
                    "authoritative": True,
                    "commit_digest": digest,
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "intents": [intent.model_dump() for intent in intents],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        fail_closed_issues = [
            str(intent.ref)[len("fail_closed:") :]
            for intent in intents
            if intent.type == "decision" and str(intent.ref).startswith("fail_closed:")
        ]
        commit_outcome = "fail_closed" if fail_closed_issues else "ok"
        return {
            "authoritative": True,
            "commit_digest": digest,
            "commit_outcome": commit_outcome,
            "issues": fail_closed_issues,
            "artifact_refs": [str(authority_path)],
            "commit_id": f"commit-{digest[:12]}",
        }


class InteractionManager:
    def __init__(self, *, bus: StreamBus, commit_orchestrator: CommitOrchestrator, project_root: Path | None = None) -> None:
        self.bus = bus
        self.commit_orchestrator = commit_orchestrator
        self.project_root = (project_root or Path.cwd()).resolve()
        self._sessions: dict[str, InteractionSessionState] = {}
        self._turns: dict[tuple[str, str], TurnState] = {}
        self._pending_commit_intents: dict[tuple[str, str], list[CommitIntent]] = {}
        self._lock = asyncio.Lock()

    def stream_enabled(self) -> bool:
        raw = (os.getenv("ORKET_STREAM_EVENTS_V1", "false") or "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    async def start(self, session_params: dict[str, Any] | None = None) -> str:
        session_id = str(uuid.uuid4())
        async with self._lock:
            self._sessions[session_id] = InteractionSessionState(
                session_id=session_id,
                params=dict(session_params or {}),
            )
        return session_id

    async def begin_turn(self, session_id: str, input_payload: dict[str, Any] | None = None, turn_params: dict[str, Any] | None = None) -> str:
        async with self._lock:
            session = self._require_session(session_id)
            if session.active_turn_id is not None:
                raise ValueError("Linear turn policy enforced: active turn already exists")
            turn_id = str(uuid.uuid4())
            session.active_turn_id = turn_id
            self._turns[(session_id, turn_id)] = TurnState(turn_id=turn_id, canceled=asyncio.Event())
            self._pending_commit_intents[(session_id, turn_id)] = []

        await self.bus.publish(
            session_id=session_id,
            turn_id=turn_id,
            event_type=StreamEventType.TURN_ACCEPTED,
            payload={
                "authoritative": False,
                "input": dict(input_payload or {}),
                "turn_params": dict(turn_params or {}),
            },
        )
        return turn_id

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        return await self.bus.subscribe(session_id)

    async def cancel(self, target_id: str) -> None:
        async with self._lock:
            # target may be session_id or turn_id
            if target_id in self._sessions:
                session = self._sessions[target_id]
                if session.active_turn_id is None:
                    return
                session_id = target_id
                turn_id = session.active_turn_id
            else:
                turn_match = None
                for (sid, tid), state in self._turns.items():
                    if tid == target_id:
                        turn_match = (sid, tid, state)
                        break
                if turn_match is None:
                    return
                session_id, turn_id, _ = turn_match

            turn_state = self._turns.get((session_id, turn_id))
            if turn_state is None:
                return
            if turn_state.terminal_event == StreamEventType.TURN_FINAL.value:
                return
            if turn_state.terminal_event is not None:
                return
            turn_state.canceled.set()
            turn_state.terminal_event = StreamEventType.TURN_INTERRUPTED.value

        await self.bus.publish(
            session_id=session_id,
            turn_id=turn_id,
            event_type=StreamEventType.TURN_INTERRUPTED,
            payload={"authoritative": False, "reason": "canceled"},
        )

    async def finalize(self, session_id: str, turn_id: str) -> CommitHandle:
        async with self._lock:
            self._require_session(session_id)
            turn_state = self._require_turn(session_id, turn_id)
            if turn_state.terminal_event is None:
                turn_state.terminal_event = StreamEventType.TURN_FINAL.value
                emit_turn_final = True
            else:
                emit_turn_final = False
            start_commit = not turn_state.commit_started
            if start_commit:
                turn_state.commit_started = True

        if emit_turn_final:
            await self.bus.publish(
                session_id=session_id,
                turn_id=turn_id,
                event_type=StreamEventType.TURN_FINAL,
                payload={"authoritative": False},
            )

        handle = CommitHandle(
            session_id=session_id,
            turn_id=turn_id,
            requested_at_mono_ts_ms=mono_ts_ms_now(),
        )
        if start_commit:
            asyncio.create_task(self._run_commit(session_id=session_id, turn_id=turn_id))
        return handle

    async def close(self, session_id: str) -> None:
        async with self._lock:
            session = self._require_session(session_id)
            session.closed = True
            if session.active_turn_id is not None:
                self._turns.pop((session_id, session.active_turn_id), None)
                self._pending_commit_intents.pop((session_id, session.active_turn_id), None)
                await self.bus.clear_turn(session_id, session.active_turn_id)
            self._sessions.pop(session_id, None)

    async def create_context(self, session_id: str, turn_id: str) -> InteractionContext:
        async with self._lock:
            turn_state = self._require_turn(session_id, turn_id)

        async def _sink(intent: CommitIntent) -> None:
            async with self._lock:
                self._pending_commit_intents.setdefault((session_id, turn_id), []).append(intent)

        return InteractionContext(
            session_id=session_id,
            turn_id=turn_id,
            bus=self.bus,
            cancel_event=turn_state.canceled,
            commit_sink=_sink,
        )

    async def mark_tool_result(
        self,
        *,
        session_id: str,
        turn_id: str,
        tool_call_id: str,
        tool_name: str,
        canceled: bool,
        side_effects_may_have_occurred: bool,
    ) -> None:
        await self.bus.publish(
            session_id=session_id,
            turn_id=turn_id,
            event_type=StreamEventType.TOOL_CALL_RESULT,
            payload={
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "canceled": canceled,
                "side_effects_may_have_occurred": side_effects_may_have_occurred if canceled else False,
                "authoritative": False,
            },
        )

    async def _run_commit(self, *, session_id: str, turn_id: str) -> None:
        async with self._lock:
            intents = list(self._pending_commit_intents.get((session_id, turn_id), []))
        if not intents:
            intents = [CommitIntent(type="turn_finalize", ref=turn_id)]

        outcome = await self.commit_orchestrator.commit(session_id=session_id, turn_id=turn_id, intents=intents)
        payload = dict(outcome)
        payload["authoritative"] = True
        await self.bus.publish(
            session_id=session_id,
            turn_id=turn_id,
            event_type=StreamEventType.COMMIT_FINAL,
            payload=payload,
        )

        trace_root = self.project_root / "workspace" / "interactions" / session_id / turn_id
        trace_root.mkdir(parents=True, exist_ok=True)
        trace_path = trace_root / "interaction_trace.jsonl"
        trace_path.write_text(
            json.dumps({"authoritative": False, "event": "turn_finalized", "turn_id": turn_id}) + "\n",
            encoding="utf-8",
        )

        async with self._lock:
            session = self._sessions.get(session_id)
            if session is not None and session.active_turn_id == turn_id:
                session.active_turn_id = None

    def _require_session(self, session_id: str) -> InteractionSessionState:
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Unknown session '{session_id}'")
        if session.closed:
            raise ValueError(f"Session '{session_id}' is closed")
        return session

    def _require_turn(self, session_id: str, turn_id: str) -> TurnState:
        turn = self._turns.get((session_id, turn_id))
        if turn is None:
            raise ValueError(f"Unknown turn '{turn_id}' in session '{session_id}'")
        return turn
