# RuntimeOS Sessions Context-Provider Pipeline Requirements
Last updated: 2026-04-01
Status: Completed archived scoped requirements companion
Owner: Orket Core
Lane type: RuntimeOS / sessions plus context-provider pipeline requirements

Paired archived implementation authority: `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_IMPLEMENTATION_PLAN.md`

Historical staging source:
1. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

Completed predecessor lane:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`

Active durable baseline:
1. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`

## Authority posture

This document is the archived scoped requirements companion for the completed RuntimeOS `sessions plus context-provider pipeline` lane.

It records the accepted bounded requirements that fed the archived implementation lane closeout.
It does not, by itself, widen the active session-boundary spec, create a memory platform, reopen the lane, or authorize a new session endpoint family.

## Source authorities

This requirements companion is bounded by:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_IMPLEMENTATION_PLAN.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
5. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`
6. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Purpose

Turn the current bounded Packet 1 session boundary into one explicit session-context pipeline and one operator-visible lineage surface without collapsing into a broad memory, retrieval, or replay platform.

This lane exists to answer:
1. what the canonical session-context envelope is on the admitted interaction session path
2. what provider ordering is admitted for the current Packet 1 inputs
3. what existing session-facing inspection surface will expose the assembled context lineage truthfully
4. what replay and reconstruction limits remain explicit once that pipeline is made inspectable

## Selected bounded scope

This lane is limited to:
1. one host-owned session-context envelope assembled for the admitted interaction session path rooted in `POST /v1/interactions/sessions`, `POST /v1/interactions/{session_id}/turns`, `InteractionManager.begin_turn(...)`, and `InteractionContext.packet1_context()`
2. one explicit provider ordering for the currently admitted Packet 1 families only:
   1. host continuity inputs: `session_id` and `session_params`
   2. turn request inputs: `input_config`, `turn_params`, `workload_id`, `department`, and contained `workspace`
   3. host-resolved extension-manifest `required_capabilities` when the extension path is used
3. one operator-visible lineage surface on the existing session-facing inspection family so the assembled session context is inspectable without creating new continuation authority
4. one replay and reconstruction rule for the assembled context on the admitted session replay and snapshot surfaces
5. one bounded change-surface family spanning `orket/interfaces/routers/sessions.py`, `orket/streaming/manager.py`, the session-facing API surfaces in `orket/interfaces/api.py`, and the built-in or extension workload paths that consume `InteractionContext.packet1_context()`

## Non-goals

This lane does not:
1. create a broad memory, search, or retrieval platform
2. define profile-memory or workspace-memory read or write product behavior
3. add new context-provider families beyond the current Packet 1 vocabulary
4. add session deletion, retention TTL, or workspace-cleanup policy
5. add replay, approval, or session continuation authority
6. add a new session endpoint family
7. add client-owned or extension-owned provider plugins that bypass host-owned session-context assembly

## Decision lock

The following remain fixed while this lane is active:
1. `session_id` remains the canonical host-owned continuity identifier
2. the admitted Packet 1 vocabulary remains bounded by `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md` until a same-change authority update says otherwise
3. session memory, profile memory, and workspace memory remain distinct authority seams
4. provider ordering and provider outputs remain host-owned even when caller payloads or extension manifests contribute raw inputs
5. replay, snapshot, comparison, and parity surfaces remain inspection-only and do not create execution or continuation authority
6. extension-manifest `required_capabilities` remains host-resolved metadata, not a caller-owned freeform field
7. authenticated operator context remains on separately governed approval surfaces and does not silently widen this lane
8. the existing session-facing route family remains canonical; if payloads change, the same change must update the active route contract docs rather than silently inventing a second surface

## Current truthful starting point

The current bounded sessions posture is:
1. `orket/interfaces/routers/sessions.py` currently assembles a raw `context_inputs` dict from admitted Packet 1 fields on `POST /v1/interactions/{session_id}/turns`
2. `orket/streaming/manager.py` currently stores that dict on `TurnState.context_inputs`, and `InteractionContext.packet1_context()` merges it with host-owned `session_params`
3. built-in and extension turn execution already consume that assembled Packet 1 context through the admitted interaction path
4. current proof already covers bounded Packet 1 context exposure and host-resolved extension `required_capabilities` on the interaction session path
5. the still-open gap is that provider ordering, provider lineage, and session-facing inspection of the assembled context are not yet named as one canonical active lane authority

## Requirements

### SCP-01. Canonical session-context envelope

The lane must define one canonical session-context envelope used across the admitted interaction session path.

That envelope must:
1. preserve the distinction between host-owned continuity inputs and per-turn request inputs
2. preserve the contained workspace rule already enforced on the admitted turn path
3. carry host-resolved extension-manifest `required_capabilities` only when the extension path is used
4. stay small enough to remain inspectable and replay-safe on the admitted session surfaces

### SCP-02. Explicit provider ordering

The lane must define one explicit provider ordering for the admitted Packet 1 inputs only.

That ordering must:
1. stay limited to host continuity inputs, turn request inputs, and host-resolved extension capability metadata
2. be stable enough that replay or snapshot surfaces can describe it without inferring hidden authority
3. fail closed if a later change tries to smuggle in additional provider families without same-change authority updates

### SCP-03. Scope separation

The lane must keep the minimum non-collapse boundary explicit between:
1. session memory
2. profile memory
3. workspace memory

No selected session-context provider may treat those scopes as interchangeable identity or authority seams.

### SCP-04. Operator-visible lineage surface

The lane must define the minimum session-facing inspection surface that exposes:
1. the assembled session-context envelope
2. the provider ordering or lineage used to assemble it
3. the inspection-only nature of that surface

The promoted slice must prefer the existing session-facing route family rather than inventing a second operator surface.

### SCP-05. Replay and reconstruction boundary

The lane must define how session replay and session snapshot surfaces may inspect the assembled context without becoming execution or continuation authority.

At minimum it must keep explicit:
1. timeline replay versus targeted replay boundaries
2. session snapshot inspection-only behavior
3. the rule that replayed or reconstructed context may describe prior continuity but may not reauthorize execution

### SCP-06. Proof expectation

The selected sessions slice is not ready to close unless one truthful proof set exists for:
1. built-in interaction turns using the canonical session-context envelope
2. extension interaction turns including host-resolved `required_capabilities`
3. stable provider ordering or lineage on the selected session-facing inspection surface
4. fail-closed behavior for contained-workspace violations, unsupported workloads, or attempts to widen the admitted provider vocabulary

Current proof baseline for this lane is:
1. `python -m pytest -q tests/interfaces/test_api_interactions.py`
2. `python -m pytest -q tests/streaming/test_manager.py`
3. `python -m pytest -q tests/interfaces/test_api.py -k "session_snapshot or session_replay_endpoint or session_halt_endpoint or interaction_cancel_endpoint"`
4. `python -m pytest -q tests/interfaces/test_sessions_router_protocol_replay.py`

### SCP-07. Same-change update targets

If this lane changes materially, the same change must update:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_REQUIREMENTS.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_IMPLEMENTATION_PLAN.md`
4. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md` when the admitted session or provider boundary changes
5. `docs/API_FRONTEND_CONTRACT.md` when session-facing routes or payloads change
6. `CURRENT_AUTHORITY.md` when active session continuity or provider-pipeline authority changes
7. `docs/RUNBOOK.md` when operator-visible session inspection, replay, snapshot, halt, or cancel behavior changes

## Requirements completion gate

This requirements companion is complete only when:
1. one canonical session-context envelope is explicit for the admitted interaction session path
2. one bounded provider ordering is explicit for the admitted Packet 1 vocabulary
3. one operator-visible lineage surface is explicit without creating a new continuation authority seam
4. replay and reconstruction limits remain explicit and inspection-only
5. the same-change update targets above are named truthfully for the selected slice

## Stop conditions

Stop and narrow scope if:
1. the lane starts reading like a broad memory or retrieval platform
2. a proposed provider family goes beyond the admitted Packet 1 vocabulary
3. session, profile, and workspace memory begin collapsing into one authority seam
4. replay or snapshot begins to read like execution or continuation authority
5. the only way forward appears to be adding a second session endpoint family
