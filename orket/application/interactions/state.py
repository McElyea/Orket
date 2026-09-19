"""Mutable interaction authority, owned by one application and event loop."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from orket.core.contracts.interaction_context import (
    SESSION_CONTEXT_VERSION,
    build_packet1_context_envelope,
    build_packet1_provider_lineage,
)
from orket.core.contracts.interaction_stream import CommitHandle, CommitIntent


@dataclass
class InteractionSessionState:
    session_id: str
    params: dict[str, Any]
    created_at: str
    updated_at: str
    active_turn_id: str | None = None
    closed: bool = False
    closing: bool = False
    failure: str | None = None
    last_turn_id: str | None = None
    latest_context_envelope: dict[str, Any] = field(default_factory=dict)
    latest_provider_lineage: list[dict[str, Any]] = field(default_factory=list)
    turn_history: list[dict[str, Any]] = field(default_factory=list)
    transition: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass
class TurnState:
    turn_id: str
    canceled: asyncio.Event = field(default_factory=asyncio.Event)
    terminal_event: str | None = None
    finalized_at: str | None = None
    context_envelope: dict[str, Any] = field(default_factory=dict)
    provider_lineage: list[dict[str, Any]] = field(default_factory=list)
    finalization: asyncio.Task[CommitHandle] | None = None
    workload: asyncio.Task[Any] | None = None


@dataclass
class InteractionState:
    sessions: dict[str, InteractionSessionState] = field(default_factory=dict)
    turns: dict[tuple[str, str], TurnState] = field(default_factory=dict)
    intents: dict[tuple[str, str], list[CommitIntent]] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def session(self, session_id: str) -> InteractionSessionState:
        session = self.sessions.get(session_id)
        if session is None or session.closed:
            raise ValueError(f"Unknown or closed session '{session_id}'")
        return session

    def turn(self, session_id: str, turn_id: str) -> TurnState:
        turn = self.turns.get((session_id, turn_id))
        if turn is None:
            raise ValueError(f"Unknown turn '{turn_id}' in session '{session_id}'")
        return turn


def turn_record(session: InteractionSessionState, turn_id: str) -> dict[str, Any]:
    return next(row for row in reversed(session.turn_history) if row["turn_id"] == turn_id)


def admit_turn(state: InteractionState, session: InteractionSessionState, *, turn_id: str,
               accepted_at: str, context_inputs: dict[str, Any]) -> None:
    if session.closing or session.failure:
        raise ValueError("Interaction session is closing or blocked")
    if session.active_turn_id is not None:
        raise ValueError("Linear turn policy enforced: active turn already exists")
    key = session.session_id, turn_id
    if key in state.turns:
        raise ValueError("E_INTERACTION_TURN_ID_REUSED")
    envelope = build_packet1_context_envelope(
        session_id=session.session_id, session_params=session.params, context_inputs=context_inputs,
    )
    lineage = build_packet1_provider_lineage(envelope)
    session.active_turn_id = session.last_turn_id = turn_id
    session.latest_context_envelope = deepcopy(envelope)
    session.latest_provider_lineage = deepcopy(lineage)
    session.updated_at = accepted_at
    session.turn_history.append({
        "turn_id": turn_id, "turn_index": len(session.turn_history) + 1, "status": "accepted",
        "accepted_at": accepted_at, "finalized_at": None, "terminal_event": None,
        "context_version": SESSION_CONTEXT_VERSION, "context_envelope": deepcopy(envelope),
        "provider_lineage": deepcopy(lineage), "inspection_only": True, "role": None,
    })
    state.turns[key] = TurnState(turn_id=turn_id, context_envelope=envelope, provider_lineage=lineage)
    state.intents[key] = []
