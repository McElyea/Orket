# RuntimeOS Sessions Context-Provider Pipeline Implementation Plan
Last updated: 2026-04-01
Status: Completed archived implementation authority
Owner: Orket Core
Lane type: RuntimeOS / sessions plus context-provider pipeline

Paired requirements authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_REQUIREMENTS.md`

Related durable baseline:
1. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`

Historical predecessor lane:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This document is the archived implementation authority for the completed RuntimeOS `sessions plus context-provider pipeline` lane.

The paired archived requirements companion remains `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_REQUIREMENTS.md`.
The durable session-boundary baseline remains `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`.
This record does not reopen the completed session-continuity closeout or create active roadmap authority.

## Source authorities

This plan is bounded by:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_REQUIREMENTS.md`
2. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
3. `docs/ROADMAP.md`
4. `docs/ARCHITECTURE.md`
5. `CURRENT_AUTHORITY.md`
6. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`
7. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Purpose

Implement one explicit host-owned session-context pipeline on the admitted interaction session path so the current Packet 1 continuity boundary stops depending on an implicit `context_inputs` blob and gains one truthful session-facing lineage surface.

This lane exists to deliver:
1. one canonical session-context envelope reused by built-in and extension interaction turns
2. one explicit provider ordering for the admitted Packet 1 input families
3. one operator-visible lineage surface on the existing session-facing inspection family
4. one replay and reconstruction boundary that stays inspection-only

## Selected bounded scope

This lane is limited to:
1. extracting one canonical session-context assembly contract across `orket/interfaces/routers/sessions.py` and `orket/streaming/manager.py`
2. preserving the current admitted Packet 1 vocabulary while making its provider ordering explicit
3. exposing session-context lineage on the existing session-facing inspection family, preferring session snapshot or closely related existing surfaces over a new route family
4. keeping built-in and extension interaction turns on the same canonical session-context envelope
5. preserving the current bounded replay, halt, and cancel posture except where the selected lineage surface must describe the session-context assembly truthfully

## Non-goals

This lane does not:
1. create a broad memory or retrieval platform
2. define profile-memory or workspace-memory lifecycle behavior
3. add new context-provider families beyond the current Packet 1 vocabulary
4. add a new session endpoint family
5. add replay, approval, or session continuation authority
6. reopen governed turn-tool approval continuation
7. broaden into Companion or frontend product UX work

## Decision lock

The following remain frozen while this lane is active:
1. `session_id` remains the host-owned continuity identifier
2. session, profile, and workspace memory remain distinct authority seams
3. the admitted Packet 1 vocabulary remains bounded by `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md` unless same-change authority updates say otherwise
4. provider ordering stays host-owned and explicit
5. extension-manifest `required_capabilities` remains host-resolved metadata only
6. replay, snapshot, comparison, and parity views remain inspection-only
7. no second session-facing route family is admitted by implication

## Current truthful starting point

The current implementation baseline is:
1. the interaction sessions router already enforces the admitted turn-start payload shape and contained workspace rule
2. the streaming manager already persists turn-local context inputs and exposes them through `InteractionContext.packet1_context()`
3. built-in and extension interaction turns already consume the same Packet 1 context surface
4. session-facing status, replay, snapshot, halt, and cancel routes already exist, but they do not yet tell one explicit session-context lineage story

## Current proof baseline

Current proof entrypoints for the selected slice are:
1. `python -m pytest -q tests/interfaces/test_api_interactions.py`
2. `python -m pytest -q tests/streaming/test_manager.py`
3. `python -m pytest -q tests/interfaces/test_api.py -k "session_snapshot or session_replay_endpoint or session_halt_endpoint or interaction_cancel_endpoint"`
4. `python -m pytest -q tests/interfaces/test_sessions_router_protocol_replay.py`

## Current change-surface baseline

The current change surface for this lane is:
1. `orket/interfaces/routers/sessions.py`
2. `orket/streaming/manager.py`
3. `orket/interfaces/api.py`
4. built-in or extension workload paths that consume `InteractionContext.packet1_context()`
5. `tests/interfaces/test_api_interactions.py`
6. `tests/streaming/test_manager.py`
7. `tests/interfaces/test_api.py`
8. `tests/interfaces/test_sessions_router_protocol_replay.py`

## Execution plan

### Step 1 - Canonical session-context envelope

Deliver:
1. one explicit session-context envelope shape on the admitted interaction turn path
2. one stable distinction between host continuity inputs, turn request inputs, and host-resolved extension capability metadata
3. one shared consumption path for built-in and extension interaction turns

### Step 2 - Provider ordering and lineage surface

Deliver:
1. one explicit provider ordering for the admitted Packet 1 vocabulary
2. one session-facing inspection surface that exposes the assembled context lineage truthfully
3. one bounded contract for how that lineage is named on snapshot or closely related existing session surfaces

### Step 3 - Replay and boundary hardening

Deliver:
1. one explicit replay and reconstruction rule for the assembled session context
2. fail-closed handling for contained-workspace violations, unsupported workloads, and attempted provider-vocabulary widening
3. same-change alignment across session-boundary docs, API contract docs, runbook guidance, and current authority snapshots when the lane changes durable behavior

## Same-change update targets

If this lane changes materially, the same change must update:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_REQUIREMENTS.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_IMPLEMENTATION_PLAN.md`
4. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md` when the admitted session or provider boundary changes
5. `docs/API_FRONTEND_CONTRACT.md` when routes or payloads change
6. `CURRENT_AUTHORITY.md` when active session continuity or provider-pipeline authority changes
7. `docs/RUNBOOK.md` when operator-visible session inspection, replay, snapshot, halt, or cancel behavior changes

## Lane completion gate

This lane is complete only when:
1. one canonical session-context envelope is explicit and shared across the admitted interaction turn path
2. one explicit provider ordering exists for the admitted Packet 1 vocabulary
3. one session-facing lineage surface exposes that assembly truth without becoming a continuation authority seam
4. replay and reconstruction boundaries remain inspection-only and explicit
5. the same-change authority docs above remain aligned with the shipped behavior

## Stop conditions

Stop and narrow scope if:
1. the lane starts reading like a broad memory or retrieval platform
2. a proposed change widens provider input families beyond the admitted Packet 1 vocabulary
3. session, profile, and workspace memory begin collapsing into one authority seam
4. replay or snapshot begins to claim execution or continuation authority
5. the lane cannot proceed without inventing a second session-facing endpoint family
