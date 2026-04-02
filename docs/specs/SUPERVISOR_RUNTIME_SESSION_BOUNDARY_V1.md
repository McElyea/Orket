# Supervisor Runtime Session Boundary V1

Last updated: 2026-04-01
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`
Implementation closeout authority:
1. `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/CLOSEOUT.md`

Related authority:
1. `docs/API_FRONTEND_CONTRACT.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/RUNBOOK.md`

## Authority posture

This document is the active durable contract authority for the completed Packet 1, RuntimeOS session continuity boundary, and the completed RuntimeOS sessions context-provider pipeline lane.

It extracts the selected host-owned `session_id` continuity model from the completed SupervisorRuntime Packet 1 lane, the completed RuntimeOS session continuity hardening lane, and the completed RuntimeOS sessions context-provider pipeline lane.
It does not define broad retention, cleanup, replay, parity, or memory-product behavior beyond the selected bounded session-continuity slice.

## Purpose

Define one host-owned session continuity boundary so turn continuity, one canonical Packet 1 session-context envelope, explicit provider ordering, session inspection surfaces, and replay or reconstruction limits remain explicit without collapsing into a broad memory platform.

## Scope

In scope:
1. host-owned `session_id` creation on `POST /v1/interactions/sessions`
2. subordinate turn attachment on `POST /v1/interactions/{session_id}/turns`
3. one bounded context-provider input vocabulary, one canonical session-context envelope, and one explicit provider ordering for the selected Packet 1 slice
4. host-owned session inspection on `GET /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}/status`, `GET /v1/sessions/{session_id}/replay`, and `GET /v1/sessions/{session_id}/snapshot`
5. protocol replay and parity surfaces under `GET /v1/protocol/*` as inspection-only reconstruction and comparison views
6. cleanup-adjacent operator commands limited to `POST /v1/sessions/{session_id}/halt` and `POST /v1/interactions/{session_id}/cancel`

Out of scope:
1. broad session cleanup, deletion, or retention policy
2. profile-memory product features
3. broad replay infrastructure beyond the selected inspection-only reconstruction and comparison surfaces
4. any rule that lets a client repo become the authority seam for continuity or lifecycle decisions
5. any rule that turns replay, reconstruction, or parity views into execution or continuation authority

## Decision lock

The following remain fixed for this bounded session-continuity contract:
1. `session_id` is the continuity identifier
2. session identity remains distinct from invocation identity and subordinate identifiers such as `turn_id`, `approval_id`, `issue_id`, and step or attempt identifiers
3. session memory, profile memory, and workspace memory must not collapse into one authority seam
4. replay, reconstruction, comparison, and parity views do not grant execution or continuation authority
5. halt and cancel remain cleanup-adjacent operator commands only and do not imply deletion or workspace cleanup
6. continuity remains host-owned even when client repos request or present session state
7. caller-provided workspace, `runs_root`, and SQLite-path inputs on the admitted surfaces must remain contained under the resolved workspace root or fail closed

## Canonical continuity boundary

The admitted host-owned continuity boundary is:
1. `POST /v1/interactions/sessions` creates the host-owned `session_id`
2. `POST /v1/interactions/{session_id}/turns` attaches subordinate turn execution to that session
3. `GET /v1/sessions/{session_id}` and `GET /v1/sessions/{session_id}/status` are host-owned inspection views keyed by that canonical `session_id`
4. `GET /v1/sessions/{session_id}/snapshot` returns an inspection-only continuity view keyed by the same host-owned `session_id`; on the admitted interaction-session path it exposes the latest session-context envelope plus ordered provider lineage for the bounded Packet 1 vocabulary
5. when `GET /v1/sessions/{session_id}/replay` is called without both `issue_id` and `turn_index`, it returns a timeline view; on the admitted interaction-session path that timeline is the interaction-turn lineage view
6. when `GET /v1/sessions/{session_id}/replay` is called with both `issue_id` and `turn_index`, it returns targeted replay for run-session surfaces only; interaction sessions fail closed on targeted replay requests
7. `approval_id`, `turn_id`, `issue_id`, and step identifiers remain subordinate targeting or execution identifiers and must not replace `session_id` as the continuity boundary

## Context-provider input contract

For the selected session-continuity slice, context-provider inputs stay limited to:
1. `session_params`
2. `input_config`
3. `turn_params`
4. `workload_id`
5. `department`
6. `workspace`
7. resolved extension-manifest `required_capabilities` when the extension path is used
8. authenticated operator context only where approval resolution is involved on separately governed approval surfaces

`required_capabilities` is host-resolved manifest metadata, not a caller-owned freeform input.
This contract does not authorize broader context-provider vocabularies without same-change spec updates.

## Canonical session-context envelope and provider ordering

For the admitted interaction-session path, the canonical Packet 1 session-context envelope is:
1. `context_version`
2. `continuity`:
   1. `session_id`
   2. `session_params`
3. `turn_request`:
   1. `input_config`
   2. `turn_params`
   3. `workload_id`
   4. `department`
   5. contained `workspace`
4. `extension_manifest.required_capabilities` only when the extension path is used

The admitted provider ordering is fixed to:
1. host continuity
2. host-validated turn request
3. host-resolved extension-manifest `required_capabilities` metadata when present

This ordering is inspection-only lineage.
It does not create continuation authority, and it must not widen beyond the bounded Packet 1 vocabulary without same-change contract updates.

## Memory-scope separation rule

This contract fixes the minimum non-collapse rule:
1. session memory is host-owned continuity attached to the `session_id`
2. profile memory is any profile-scoped or operator-scoped memory outside the session object
3. workspace memory is filesystem or workspace-path state under the selected workspace root
4. those scopes may interact, but they must not be treated as interchangeable identity or authority seams

This contract does not standardize full read, write, clear, or retirement policy for each scope.
It only makes the boundary explicit enough for the selected Packet 1 slice to remain truthful.

## Inspection, replay, and cleanup-adjacent boundary

The admitted operator-visible boundary is:
1. `GET /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}/status`, `GET /v1/sessions/{session_id}/replay`, and `GET /v1/sessions/{session_id}/snapshot` are session inspection surfaces only
2. on the admitted interaction-session path, `GET /v1/sessions/{session_id}/snapshot` exposes the latest session-context envelope and ordered provider lineage only as inspection truth
3. on the admitted interaction-session path, `GET /v1/sessions/{session_id}/replay` without targeted replay selectors exposes an interaction-turn lineage timeline only as inspection truth
4. `POST /v1/sessions/{session_id}/halt` is the admitted session-scoped cleanup-adjacent operator command on this contract
5. `POST /v1/interactions/{session_id}/cancel` is the admitted interaction-scoped cleanup-adjacent operator command and may target the whole interaction session or one subordinate `turn_id`
6. halt and cancel remain bounded operator commands; they do not define session deletion, retention expiry, workspace cleanup, or broader cleanup policy
7. preserved session artifacts may describe prior continuity, but they do not invent new continuation authority
8. a client-facing surface may present session state, but the host remains authoritative for continuity and lifecycle decisions

## Protocol replay and parity boundary

For the admitted protocol surfaces:
1. `GET /v1/protocol/runs/{run_id}/replay` reconstructs one protocol run for inspection only
2. `GET /v1/protocol/replay/compare` and `GET /v1/protocol/replay/campaign` compare protocol replay outputs for inspection only
3. `GET /v1/protocol/runs/{run_id}/ledger-parity` and `GET /v1/protocol/ledger-parity/campaign` compare protocol versus SQLite ledger projections for inspection only
4. replay, comparison, campaign, and ledger-parity outputs may report mismatch, uncertainty, or drift, but they do not become execution or continuation authority
5. caller-provided `runs_root` and `sqlite_db_path` inputs remain bounded by the resolved workspace root

## Fail-closed rules

The selected session boundary must fail closed when:
1. a requested workspace path escapes the resolved workspace root
2. a requested `runs_root` or SQLite path escapes the resolved workspace root on the admitted protocol surfaces
3. the target workload id is missing or unsupported for the selected turn path
4. a client attempts to substitute subordinate identifiers for the host-owned `session_id`
5. a later surface tries to treat replay, reconstruction, comparison, or parity artifacts as execution or continuation authority
6. a halt request targets a missing `session_id` on the admitted session halt path
7. targeted replay selectors are used against an admitted interaction session rather than a run-session replay surface

## Canonical seams and proof entrypoints

Current seams:
1. `POST /v1/interactions/sessions`
2. `POST /v1/interactions/{session_id}/turns`
3. `GET /v1/sessions/{session_id}`
4. `GET /v1/sessions/{session_id}/status`
5. `GET /v1/sessions/{session_id}/replay`
6. `GET /v1/sessions/{session_id}/snapshot`
7. `POST /v1/sessions/{session_id}/halt`
8. `POST /v1/interactions/{session_id}/cancel`
9. `GET /v1/protocol/runs/{run_id}/replay`
10. `GET /v1/protocol/replay/compare`
11. `GET /v1/protocol/replay/campaign`
12. `GET /v1/protocol/runs/{run_id}/ledger-parity`
13. `GET /v1/protocol/ledger-parity/campaign`

Current proof entrypoints:
1. `python -m pytest -q tests/interfaces/test_api_interactions.py`
2. `python -m pytest -q tests/streaming/test_manager.py`
3. `python -m pytest -q tests/interfaces/test_sessions_router_protocol_replay.py`
4. `python -m pytest -q tests/interfaces/test_api.py -k "run_detail_and_session_status or session_halt_endpoint or interaction_cancel_endpoint or session_replay_endpoint or session_snapshot"`

## Contract maintenance rules

If this contract changes materially, the same change must update:
1. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
2. `docs/API_FRONTEND_CONTRACT.md` when session or turn routes or payloads change
3. `CURRENT_AUTHORITY.md` when the active spec set or continuity boundary changes
4. `docs/RUNBOOK.md` when operator-visible session inspection, replay, parity, or cleanup behavior changes
