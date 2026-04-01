# RuntimeOS Session Continuity Implementation Plan
Last updated: 2026-04-01
Status: Completed (archived session-continuity hardening lane)
Owner: Orket Core
Lane type: RuntimeOS / host-owned session continuity and context-provider hardening

Closeout authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`

Requirements authority:
1. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`

Contract delta:
1. `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_SESSION_CONTINUITY_CLOSEOUT_2026-04-01.md`

Related authority:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/API_FRONTEND_CONTRACT.md`
5. `docs/RUNBOOK.md`
6. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This document is the archived lane record for the completed RuntimeOS session continuity hardening lane.

The durable contract authority remains `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`.
The closeout record now lives at `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`.
This archived record preserves the bounded lane logic used to close the RuntimeOS follow-on lane.
It no longer acts as active roadmap authority.

## Purpose

Harden one host-owned session continuity lane that keeps `session_id` canonical, keeps context-provider inputs explicit, and keeps replay or reconstruction surfaces inspection-only.

This lane exists to answer:
1. what the canonical host-owned session continuity boundary is across the current interaction and session surfaces
2. what operator-visible inspection and cleanup-adjacent commands are admitted for that boundary
3. what replay and reconstruction surfaces remain explicitly non-authoritative
4. what proof and same-change doc updates are required before this lane can close

## Selected bounded scope

This lane is limited to:
1. host-owned `session_id` creation on `POST /v1/interactions/sessions`
2. subordinate turn attachment on `POST /v1/interactions/{session_id}/turns`
3. bounded Packet 1 context-provider inputs surfaced through the interaction context, including extension-manifest `required_capabilities` when the extension path is used
4. operator-visible session inspection surfaces on `GET /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}/status`, `GET /v1/sessions/{session_id}/replay`, and `GET /v1/sessions/{session_id}/snapshot`
5. protocol replay and parity surfaces under `orket/interfaces/routers/sessions.py` as non-authoritative reconstruction and comparison views only
6. cleanup-adjacent operator commands limited to `POST /v1/sessions/{session_id}/halt` and `POST /v1/interactions/{session_id}/cancel`

## Non-goals

This lane does not:
1. create a broad memory platform
2. define profile-memory or workspace-memory product behavior
3. define session deletion, retention TTLs, or artifact cleanup policy
4. turn protocol replay or ledger-parity views into execution authority
5. reopen governed turn-tool approval continuation

## Decision lock

The following remain fixed while this lane is active:
1. `session_id` remains the canonical continuity identifier and stays distinct from subordinate identifiers such as `turn_id`, `approval_id`, `issue_id`, and step or attempt ids
2. context-provider inputs stay bounded by `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
3. session memory, profile memory, and workspace memory remain distinct authority seams
4. replay, reconstruction, comparison, and parity views remain inspection-only and must not create continuation authority
5. halt and cancel remain the only admitted cleanup-adjacent operator commands on this lane; they do not imply session deletion or workspace cleanup
6. workspace-root containment remains fail-closed for caller-provided workspace, runs-root, and SQLite-path inputs on this lane

## Current admitted proof baseline

1. `tests/interfaces/test_api_interactions.py` covers host-owned session start, bounded turn attachment, bounded Packet 1 context inputs, extension-manifest `required_capabilities`, and interaction-stream behavior
2. `tests/interfaces/test_sessions_router_protocol_replay.py` covers protocol replay, replay comparison, replay campaigns, ledger parity, parity campaigns, and fail-closed workspace-path containment on those surfaces
3. `tests/interfaces/test_api.py` covers authenticated session halt and authenticated interaction cancel operator-command publication on the current API path

## Current change-surface baseline

1. `orket/interfaces/routers/sessions.py`
2. `orket/interfaces/api.py`
3. `orket/streaming/manager.py`
4. `orket/application/services/protocol_replay_service.py`
5. `orket/orchestration/engine.py`
6. `orket/orchestration/engine_services.py`
7. `orket/extensions/manager.py`

## Hardening focus used for closeout

1. keep one outward session continuity story across interaction start or turn, session detail or status, session replay or snapshot, and authenticated halt or cancel
2. keep the Packet 1 context-provider vocabulary explicit for both built-in and extension-backed workloads
3. keep replay, comparison, and parity surfaces explicitly non-authoritative while preserving fail-closed path containment
4. avoid silent drift between the session boundary spec, API contract, runbook, current authority snapshot, and the shipped router behavior

## Same-change update targets

If this lane changes materially, the same change must update:
1. `docs/ROADMAP.md`
2. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md` when the selected continuity or context boundary changes
3. `docs/API_FRONTEND_CONTRACT.md` when routes or payloads change
4. `CURRENT_AUTHORITY.md` when active session continuity or operator-control authority changes
5. `docs/RUNBOOK.md` when operator-visible halt, cancel, inspection, or replay behavior changes

## Lane completion gate

This lane was complete only when:
1. one canonical host-owned session continuity story is explicit across the selected interaction and session surfaces
2. one bounded context-provider input story is explicit for both built-in and extension-backed workloads
3. one operator-visible inspection and cleanup-adjacent boundary is explicit and remains limited to the admitted surfaces above
4. one replay and reconstruction boundary is explicit and stays non-authoritative in docs and proof
5. the relevant source-of-truth docs remain aligned in the same change

## Final outcome

This lane closed successfully because:
1. the durable session-boundary contract now makes the selected inspection surfaces, cleanup-adjacent operator commands, and protocol replay or parity inspection-only boundary explicit
2. `CURRENT_AUTHORITY.md`, `docs/API_FRONTEND_CONTRACT.md`, and `docs/RUNBOOK.md` now match that bounded continuity story in the same change
3. the roadmap no longer carries an active RuntimeOS Priority Now lane after this closeout

## Stop conditions

Stop and narrow scope if:
1. this lane starts reading like a broad memory or continuity platform
2. cleanup-adjacent work expands into deletion, retention, or workspace-cleanup policy
3. replay or parity surfaces begin to claim execution or continuation authority
4. session, profile, and workspace memory begin collapsing into one authority seam
