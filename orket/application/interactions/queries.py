"""Read-only projections of application-owned interaction state."""
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from orket.core.contracts.interaction_context import SESSION_CONTEXT_VERSION

from .state import InteractionSessionState, InteractionState

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

def _session_status(session: InteractionSessionState) -> str:
    if session.closed:
        return "closed"
    if session.failure:
        return "blocked"
    if session.closing:
        return "closing"
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


class InteractionQueries:
    def __init__(self, state: InteractionState):
        self._state = state

    async def get_session_detail(self, session_id: str) -> dict[str, Any] | None:
        async with self._state.lock:
            session = self._state.sessions.get(session_id)
            if session is None or session.closed:
                return None
            return self._session_detail_payload(session)

    async def get_session_status(self, session_id: str) -> dict[str, Any] | None:
        async with self._state.lock:
            session = self._state.sessions.get(session_id)
            if session is None or session.closed:
                return None
            return {
                "session_id": session.session_id,
                "surface": "interaction_session",
                "active": session.active_turn_id is not None,
                "status": _session_status(session),
                "task_state": "blocked" if session.failure else "running" if session.active_turn_id is not None else "idle",
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
        async with self._state.lock:
            session = self._state.sessions.get(session_id)
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
        async with self._state.lock:
            session = self._state.sessions.get(session_id)
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
