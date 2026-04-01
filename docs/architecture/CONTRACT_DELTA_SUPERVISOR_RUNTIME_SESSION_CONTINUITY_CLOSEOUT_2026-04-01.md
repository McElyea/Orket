# Contract Delta: Supervisor Runtime Session Continuity Closeout

## Summary
- Change title: SupervisorRuntime session boundary realignment for RuntimeOS session continuity closeout
- Owner: Orket Core
- Date: 2026-04-01
- Affected contract(s):
  - `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
  - `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`
  - `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Delta
- Current behavior:
  - the active durable session-boundary spec already fixed host-owned `session_id`, subordinate turn attachment, bounded Packet 1 context-provider inputs, and a non-authoritative reconstruction rule
  - the active RuntimeOS session-continuity lane additionally named session inspection surfaces, protocol replay or parity inspection-only surfaces, and halt or cancel cleanup-adjacent operator commands, but those details still lived in the active lane record instead of the durable spec
  - the older RuntimeOS staging and meta-lane records still pointed at now-removed active `docs/projects/RuntimeOS/*` paths
- Proposed behavior:
  - make the durable session-boundary spec explicitly cover the admitted session inspection surfaces, the selected protocol replay and parity inspection-only surfaces, and the admitted halt or cancel cleanup-adjacent operator commands
  - keep replay, comparison, reconstruction, and parity surfaces non-authoritative and keep halt or cancel limited to operator cleanup-adjacent command authority only
  - archive the completed RuntimeOS session-continuity lane and retarget the older RuntimeOS staging and meta-lane records at the archived follow-on lane instead of dead active paths
- Why this break is required now:
  - closing the lane while the durable spec stayed narrower than the shipped and documented boundary would leave contract drift behind the archive
  - leaving the historical RuntimeOS packet and meta-lane records pointed at deleted active files would create false live authority

## Migration Plan
1. Compatibility window:
   - none; this is a same-change contract realignment and lane closeout, not a staged compatibility period
2. Migration steps:
   - expand `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md` to the completed session-continuity boundary
   - sync `CURRENT_AUTHORITY.md`, `docs/API_FRONTEND_CONTRACT.md`, and `docs/RUNBOOK.md`
   - archive the completed RuntimeOS session-continuity plan and update older RuntimeOS historical references to the archived closeout
   - remove the RuntimeOS Priority Now lane from `docs/ROADMAP.md`
3. Validation gates:
   - `python -m pytest -q tests/interfaces/test_api_interactions.py`
   - `python -m pytest -q tests/interfaces/test_sessions_router_protocol_replay.py`
   - `python -m pytest -q tests/interfaces/test_api.py -k "run_detail_and_session_status or session_halt_endpoint or interaction_cancel_endpoint or session_replay_endpoint"`
   - `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger:
   - targeted session-boundary proof or docs hygiene fails after the contract realignment
2. Rollback steps:
   - reopen the RuntimeOS session-continuity lane instead of leaving it archived
   - restore the narrower session-boundary contract posture and keep the lane active until the broader continuity story is proved or narrowed again
3. Data/state recovery notes:
   - no data migration is involved; this delta changes contract and roadmap authority only

## Versioning Decision
- Version bump type: none
- Effective version/date: 2026-04-01
- Downstream impact:
  - session-continuity consumers must treat the admitted session inspection surfaces plus protocol replay or parity views as inspection-only authority and must not invent continuation authority from them
  - future RuntimeOS work on deletion, retention, cleanup, or broader memory behavior now requires an explicit new lane instead of piggybacking on the closed session-continuity lane
