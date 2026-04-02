# Contract Delta: Supervisor Runtime Session Context Pipeline Closeout

## Summary
- Change title: RuntimeOS sessions context-provider pipeline closeout
- Owner: Orket Core
- Date: 2026-04-01
- Affected contract(s):
  - `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
  - `docs/API_FRONTEND_CONTRACT.md`
  - `docs/RUNBOOK.md`
  - `CURRENT_AUTHORITY.md`
  - `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/CLOSEOUT.md`

## Delta
- Current behavior:
  - the durable session-boundary spec already fixed host-owned `session_id`, subordinate turn attachment, bounded Packet 1 context-provider inputs, and inspection-only session surfaces
  - the interaction-session path already carried Packet 1 context through `InteractionContext.packet1_context()`, but the canonical session-context envelope, provider ordering, and session-facing lineage surface were still an active lane rather than archived contract history
  - the roadmap and future RuntimeOS packet still presented the sessions context-provider lane as active
- Proposed behavior:
  - make the durable session-boundary contract explicitly cover one canonical inspection-only session-context envelope with ordered provider lineage on the admitted interaction-session path
  - keep targeted replay with `issue_id` plus `turn_index` run-session-only and fail closed on interaction sessions
  - archive the completed RuntimeOS sessions context-provider pipeline lane and return the roadmap to maintenance-only posture
- Why this break is required now:
  - closing the lane without naming the shipped session-context envelope and lineage in durable contract authority would leave active-versus-archive drift
  - leaving the roadmap and future packet pointing at a completed active RuntimeOS lane would create false live authority

## Migration Plan
1. Compatibility window:
   - none; this is a same-change contract realignment and lane closeout
2. Migration steps:
   - ship the canonical interaction-session context envelope and provider-lineage surfaces on the existing session inspection routes
   - sync `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`, `docs/API_FRONTEND_CONTRACT.md`, `docs/RUNBOOK.md`, and `CURRENT_AUTHORITY.md`
   - archive the RuntimeOS sessions context-provider requirements and implementation plan with a closeout record
   - remove the completed RuntimeOS lane from `docs/ROADMAP.md` and retarget the future packet to the archive
3. Validation gates:
   - `python -m pytest -q tests/streaming/test_manager.py tests/interfaces/test_api_interactions.py`
   - `python -m pytest -q tests/interfaces/test_api.py -k "session_snapshot or session_replay_endpoint or run_detail_and_session_status or session_halt_endpoint or interaction_cancel_endpoint"`
   - `python -m pytest -q tests/interfaces/test_sessions_router_protocol_replay.py`
   - `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger:
   - targeted session-boundary proof or docs hygiene fails after the session-context pipeline closeout
2. Rollback steps:
   - reopen the RuntimeOS sessions context-provider pipeline lane instead of leaving it archived
   - restore the narrower session-boundary posture and keep the lane active until the session-context lineage surface is proved or narrowed again
3. Data/state recovery notes:
   - no data migration is involved; this delta changes code behavior, durable contract wording, and roadmap authority only

## Versioning Decision
- Version bump type: none
- Effective version/date: 2026-04-01
- Downstream impact:
  - session-facing consumers must treat interaction-session snapshot and timeline replay outputs as inspection-only lineage surfaces
  - targeted replay with `issue_id` plus `turn_index` remains unavailable on interaction sessions
  - future session, replay, cleanup, or broader memory work now requires an explicit new lane instead of piggybacking on this closed slice
