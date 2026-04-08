from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles

from .bus import StreamBus
from .contracts import CommitHandle, CommitIntent, StreamEvent, StreamEventType, mono_ts_ms_now
from .session_context import (
    SESSION_CONTEXT_VERSION,
    build_packet1_context_envelope,
    build_packet1_provider_lineage,
    flatten_packet1_context,
)

_INTERACTION_MEMORY_SCOPE_BOUNDARY = {
    "session_memory": "host_owned_session_continuity",
    "profile_memory": "separate_profile_or_operator_scope",
    "workspace_memory": "workspace_root_state_separate_from_session_identity",
}

_INTERACTION_REPLAY_BOUNDARY = {
    "timeline_view": "inspection_only",
    "targeted_replay": "run_session_only",
    "execution_authority": "none",
}

_INTERACTION_MEMORY_SCOPE_BOUNDARY_KEYS = frozenset(_INTERACTION_MEMORY_SCOPE_BOUNDARY)
_INTERACTION_REPLAY_BOUNDARY_KEYS = frozenset(_INTERACTION_REPLAY_BOUNDARY)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _turn_status_from_terminal_event(terminal_event: str | None) -> str:
    if terminal_event == StreamEventType.TURN_INTERRUPTED.value:
        return "interrupted"
    if terminal_event == StreamEventType.TURN_FINAL.value:
        return "finalized"
    return "accepted"


def _session_status(session: InteractionSessionState) -> str:
    if session.closed:
        return "closed"
    if session.active_turn_id is not None:
        return "active"
    return "idle"


def _validated_interaction_boundary(
    boundary: Mapping[str, str],
    *,
    required_keys: frozenset[str],
    name: str,
) -> dict[str, str]:
    actual_keys = frozenset(str(key) for key in boundary)
    if actual_keys != required_keys:
        raise RuntimeError(f"{name} keys drifted: expected={sorted(required_keys)} actual={sorted(actual_keys)}")
    return dict(boundary)


@dataclass
class InteractionSessionState:
    session_id: str
    params: dict[str, Any]
    active_turn_id: str | None = None
    closed: bool = False
    created_at: str = ""
    updated_at: str = ""
    last_turn_id: str | None = None
    latest_context_envelope: dict[str, Any] = field(default_factory=dict)
    latest_provider_lineage: list[dict[str, Any]] = field(default_factory=list)
    turn_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TurnState:
    turn_id: str
    canceled: asyncio.Event
    terminal_event: str | None = None
    commit_started: bool = False
    turn_index: int = 0
    accepted_at: str = ""
    finalized_at: str | None = None
    context_envelope: dict[str, Any] = field(default_factory=dict)
    provider_lineage: list[dict[str, Any]] = field(default_factory=list)


class InteractionContext:
    def __init__(
        self,
        *,
        session_id: str,
        turn_id: str,
        session_params: dict[str, Any],
        packet1_context_envelope: dict[str, Any],
        packet1_provider_lineage: list[dict[str, Any]],
        bus: StreamBus,
        cancel_event: asyncio.Event,
        commit_sink: Callable[[CommitIntent], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self.turn_id = turn_id
        self._session_params = deepcopy(session_params)
        self._packet1_context_envelope = deepcopy(packet1_context_envelope)
        self._packet1_provider_lineage = deepcopy(packet1_provider_lineage)
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

    def session_params(self) -> dict[str, Any]:
        return deepcopy(self._session_params)

    def packet1_context(self) -> dict[str, Any]:
        return flatten_packet1_context(self._packet1_context_envelope)

    def packet1_context_envelope(self) -> dict[str, Any]:
        return deepcopy(self._packet1_context_envelope)

    def packet1_provider_lineage(self) -> list[dict[str, Any]]:
        return deepcopy(self._packet1_provider_lineage)

    def is_canceled(self) -> bool:
        return self._cancel_event.is_set()

    async def await_cancel(self) -> None:
        await self._cancel_event.wait()


class CommitOrchestrator:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()

    @staticmethod
    async def _write_commit_artifact(path: Path, payload: dict[str, Any]) -> None:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(payload, indent=2, sort_keys=True))

    async def commit(self, *, session_id: str, turn_id: str, intents: list[CommitIntent]) -> dict[str, Any]:
        # Deterministic digest over commit inputs.
        payload = {
            "session_id": session_id,
            "turn_id": turn_id,
            "intents": [intent.model_dump() for intent in intents],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

        authority_path = (
            self.project_root / "workspace" / "interactions" / session_id / turn_id / "authority_commit.json"
        )
        await self._write_commit_artifact(
            authority_path,
            {
                "authoritative": True,
                "commit_digest": digest,
                "session_id": session_id,
                "turn_id": turn_id,
                "intents": [intent.model_dump() for intent in intents],
            },
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
    def __init__(
        self, *, bus: StreamBus, commit_orchestrator: CommitOrchestrator, project_root: Path | None = None
    ) -> None:
        self.bus = bus
        self.commit_orchestrator = commit_orchestrator
        self.project_root = (project_root or Path.cwd()).resolve()
        self._sessions: dict[str, InteractionSessionState] = {}
        self._turns: dict[tuple[str, str], TurnState] = {}
        self._pending_commit_intents: dict[tuple[str, str], list[CommitIntent]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _write_trace_line(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def stream_enabled(self) -> bool:
        raw = (os.getenv("ORKET_STREAM_EVENTS_V1", "false") or "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    async def start(self, session_params: dict[str, Any] | None = None) -> str:
        session_id = str(uuid.uuid4())
        now = _utc_now_iso()
        async with self._lock:
            self._sessions[session_id] = InteractionSessionState(
                session_id=session_id,
                params=dict(session_params or {}),
                created_at=now,
                updated_at=now,
            )
        return session_id

    async def begin_turn(
        self,
        session_id: str,
        input_payload: dict[str, Any] | None = None,
        turn_params: dict[str, Any] | None = None,
        *,
        context_inputs: dict[str, Any] | None = None,
    ) -> str:
        accepted_at = _utc_now_iso()
        async with self._lock:
            session = self._require_session(session_id)
            if session.active_turn_id is not None:
                raise ValueError("Linear turn policy enforced: active turn already exists")
            turn_id = str(uuid.uuid4())
            turn_index = len(session.turn_history) + 1
            context_envelope = build_packet1_context_envelope(
                session_id=session_id,
                session_params=session.params,
                context_inputs=dict(context_inputs or {}),
            )
            provider_lineage = build_packet1_provider_lineage(context_envelope)
            session.active_turn_id = turn_id
            session.last_turn_id = turn_id
            session.latest_context_envelope = deepcopy(context_envelope)
            session.latest_provider_lineage = deepcopy(provider_lineage)
            session.updated_at = accepted_at
            session.turn_history.append(
                {
                    "turn_id": turn_id,
                    "turn_index": turn_index,
                    "status": "accepted",
                    "accepted_at": accepted_at,
                    "finalized_at": None,
                    "terminal_event": None,
                    "context_version": SESSION_CONTEXT_VERSION,
                    "context_envelope": deepcopy(context_envelope),
                    "provider_lineage": deepcopy(provider_lineage),
                    "inspection_only": True,
                    "role": None,
                }
            )
            self._turns[(session_id, turn_id)] = TurnState(
                turn_id=turn_id,
                canceled=asyncio.Event(),
                turn_index=turn_index,
                accepted_at=accepted_at,
                context_envelope=deepcopy(context_envelope),
                provider_lineage=deepcopy(provider_lineage),
            )
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

    async def subscribe(self, session_id: str) -> asyncio.Queue[StreamEvent]:
        return await self.bus.subscribe(session_id)

    async def cancel(self, target_id: str) -> None:
        finalized_at = _utc_now_iso()
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
            turn_state.finalized_at = finalized_at
            session_state = self._sessions.get(session_id)
            if session_state is not None:
                session_state.updated_at = finalized_at
                turn_record = self._find_turn_record(session_state, turn_id)
                if turn_record is not None:
                    turn_record["terminal_event"] = StreamEventType.TURN_INTERRUPTED.value
                    turn_record["status"] = "interrupted"
                    turn_record["finalized_at"] = finalized_at

        await self.bus.publish(
            session_id=session_id,
            turn_id=turn_id,
            event_type=StreamEventType.TURN_INTERRUPTED,
            payload={"authoritative": False, "reason": "canceled"},
        )

    async def finalize(self, session_id: str, turn_id: str) -> CommitHandle:
        finalized_at = _utc_now_iso()
        async with self._lock:
            session = self._require_session(session_id)
            turn_state = self._require_turn(session_id, turn_id)
            if turn_state.terminal_event is None:
                turn_state.terminal_event = StreamEventType.TURN_FINAL.value
                turn_state.finalized_at = finalized_at
                emit_turn_final = True
                turn_record = self._find_turn_record(session, turn_id)
                if turn_record is not None:
                    turn_record["terminal_event"] = StreamEventType.TURN_FINAL.value
                    turn_record["status"] = "finalized"
                    turn_record["finalized_at"] = finalized_at
            else:
                emit_turn_final = False
            start_commit = not turn_state.commit_started
            if start_commit:
                turn_state.commit_started = True
            session.updated_at = finalized_at

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
            await self._run_commit(session_id=session_id, turn_id=turn_id)
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
            session = self._require_session(session_id)
            turn_state = self._require_turn(session_id, turn_id)

        async def _sink(intent: CommitIntent) -> None:
            async with self._lock:
                self._pending_commit_intents.setdefault((session_id, turn_id), []).append(intent)

        return InteractionContext(
            session_id=session_id,
            turn_id=turn_id,
            session_params=session.params,
            packet1_context_envelope=turn_state.context_envelope,
            packet1_provider_lineage=turn_state.provider_lineage,
            bus=self.bus,
            cancel_event=turn_state.canceled,
            commit_sink=_sink,
        )

    async def get_session_detail(self, session_id: str) -> dict[str, Any] | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.closed:
                return None
            return self._session_detail_payload(session)

    async def get_session_status(self, session_id: str) -> dict[str, Any] | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.closed:
                return None
            return {
                "session_id": session.session_id,
                "surface": "interaction_session",
                "active": session.active_turn_id is not None,
                "status": _session_status(session),
                "task_state": "running" if session.active_turn_id is not None else "idle",
                "backlog": {"count": 0, "by_status": {}},
                "summary": {
                    "continuity_identifier": "session_id",
                    "context_version": SESSION_CONTEXT_VERSION,
                    "latest_turn_id": session.last_turn_id,
                    "turn_count": len(session.turn_history),
                    "inspection_only": True,
                },
                "artifacts": {
                    "session_snapshot_surface": "GET /v1/sessions/{session_id}/snapshot",
                    "session_replay_surface": "GET /v1/sessions/{session_id}/replay",
                    "targeted_replay": "run_session_only",
                },
            }

    async def get_session_snapshot(self, session_id: str) -> dict[str, Any] | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.closed:
                return None
            return {
                **self._session_detail_payload(session),
                "snapshot_kind": "interaction_session_context",
                "captured_at": session.updated_at,
                "memory_scope_boundary": _validated_interaction_boundary(
                    _INTERACTION_MEMORY_SCOPE_BOUNDARY,
                    required_keys=_INTERACTION_MEMORY_SCOPE_BOUNDARY_KEYS,
                    name="interaction_memory_scope_boundary",
                ),
                "replay_boundary": _validated_interaction_boundary(
                    _INTERACTION_REPLAY_BOUNDARY,
                    required_keys=_INTERACTION_REPLAY_BOUNDARY_KEYS,
                    name="interaction_replay_boundary",
                ),
                "session_context_pipeline": {
                    "context_version": SESSION_CONTEXT_VERSION,
                    "provider_lineage": deepcopy(session.latest_provider_lineage),
                    "latest_context_envelope": deepcopy(session.latest_context_envelope)
                    if session.latest_context_envelope
                    else None,
                },
            }

    async def get_session_replay_timeline(self, session_id: str, *, role: str | None = None) -> dict[str, Any] | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.closed:
                return None
            role_filter = str(role or "").strip().lower() or None
            turns = [
                deepcopy(turn)
                for turn in session.turn_history
                if role_filter is None or str(turn.get("role") or "").strip().lower() == role_filter
            ]
            return {
                "session_id": session.session_id,
                "surface": "interaction_session",
                "inspection_only": True,
                "turn_count": len(turns),
                "filters": {"role": role_filter},
                "replay_boundary": _validated_interaction_boundary(
                    _INTERACTION_REPLAY_BOUNDARY,
                    required_keys=_INTERACTION_REPLAY_BOUNDARY_KEYS,
                    name="interaction_replay_boundary",
                ),
                "turns": turns,
            }

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

        trace_path = self.project_root / "workspace" / "interactions" / session_id / turn_id / "interaction_trace.jsonl"
        await asyncio.to_thread(
            self._write_trace_line,
            trace_path,
            {"authoritative": False, "event": "turn_finalized", "turn_id": turn_id},
        )

        async with self._lock:
            session = self._sessions.get(session_id)
            if session is not None and session.active_turn_id == turn_id:
                session.active_turn_id = None
                session.updated_at = _utc_now_iso()
            if session is not None:
                turn_record = self._find_turn_record(session, turn_id)
                if turn_record is not None:
                    turn_record["commit_outcome"] = str(payload.get("commit_outcome") or "")
                    turn_record["commit_id"] = str(payload.get("commit_id") or "")
                    turn_record["authoritative_commit"] = bool(payload.get("authoritative", False))
        await self.bus.purge_turn(session_id, turn_id, drain_subscriber_queues=False)

    def _find_turn_record(self, session: InteractionSessionState, turn_id: str) -> dict[str, Any] | None:
        for turn in reversed(session.turn_history):
            if str(turn.get("turn_id") or "") == turn_id:
                return turn
        return None

    def _session_detail_payload(self, session: InteractionSessionState) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "surface": "interaction_session",
            "continuity_identifier": "session_id",
            "inspection_only": True,
            "status": _session_status(session),
            "active_turn_id": session.active_turn_id,
            "latest_turn_id": session.last_turn_id,
            "turn_count": len(session.turn_history),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "session_params": deepcopy(session.params),
        }

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
