# Contract Delta: Supervisor Runtime Create Issue Approval Continuation Closeout

## Summary
- Change title: RuntimeOS `create_issue` approval continuation closeout
- Owner: Orket Core
- Date: 2026-04-01
- Affected contract(s):
  - `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
  - `docs/API_FRONTEND_CONTRACT.md`
  - `docs/RUNBOOK.md`
  - `CURRENT_AUTHORITY.md`
  - `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/CLOSEOUT.md`

## Delta
- Current behavior:
  - the durable approval-checkpoint contract already admitted the governed kernel `NEEDS_APPROVAL` slice and the governed turn-tool `write_file` continuation slice
  - the active RuntimeOS lane still treated approval continuation beyond `write_file` as open work rather than archived contract history
  - the turn-tool approval continuation service was still named for the bounded `write_file` predecessor lane even though the generic `tool_approval` request family already existed
- Proposed behavior:
  - admit one additional bounded governed turn-tool approval-required continuation slice for `create_issue` on the existing default `issue:<issue_id>` path
  - keep the existing `tool_approval` list, detail, and decision surfaces and the existing `control_plane_target_ref`
  - continue or terminal-stop the same governed turn-tool run on approval or denial without widening into a broader approval-required tool family or manual resume API
  - archive the completed RuntimeOS approval-continuation lane and return the roadmap to maintenance-only posture
- Why this break is required now:
  - closing the lane without naming the selected `create_issue` slice in durable contract authority would leave runtime truth and active docs drifting
  - leaving the roadmap and future packet pointing at an already-shipped active RuntimeOS lane would create false live authority

## Migration Plan
1. Compatibility window:
   - none; this is a same-change contract realignment and lane closeout
2. Migration steps:
   - ship the generic admitted governed turn-tool approval continuation service for the selected `create_issue` slice plus the already-shipped `write_file` slice
   - sync `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`, `docs/API_FRONTEND_CONTRACT.md`, `docs/RUNBOOK.md`, and `CURRENT_AUTHORITY.md`
   - archive the RuntimeOS approval-continuation requirements and implementation plan with a closeout record
   - remove the completed RuntimeOS lane from `docs/ROADMAP.md` and retarget the future packet to the archive
3. Validation gates:
   - `python -m pytest -q tests/application/test_turn_executor_middleware.py -k "approval_resume_continues_same_governed_run or approval_required_tool"`
   - `python -m pytest -q tests/application/test_engine_approvals.py`
   - `python -m pytest -q tests/application/test_turn_tool_dispatcher.py`
   - `python -m pytest -q tests/application/test_orchestrator_epic.py -k "pending_gate_callback_creates_tool_approval_request or pending_gate_callback_creates_create_issue_tool_approval_request"`
   - `python -m pytest -q tests/interfaces/test_api_approvals.py tests/interfaces/test_api_approval_projection_fail_closed.py`
   - `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger:
   - targeted approval-continuation proof or docs hygiene fails after the `create_issue` lane closeout
2. Rollback steps:
   - reopen the RuntimeOS approval-continuation lane instead of leaving it archived
   - restore the narrower approval-checkpoint posture and keep the lane active until the selected slice is proved or narrowed again
3. Data/state recovery notes:
   - no data migration is involved; this delta changes code behavior, durable contract wording, and roadmap authority only

## Versioning Decision
- Version bump type: none
- Effective version/date: 2026-04-01
- Downstream impact:
  - operators must treat the approval surface as admitting one additional bounded governed turn-tool `create_issue` continuation slice beyond the shipped `write_file` slice
  - the selected turn-tool slice remains inspection-plus-decision on the existing approval routes and same-run continuation or terminal stop only
  - future approval expansion beyond `write_file` plus `create_issue` still requires an explicit new lane instead of piggybacking on this closed slice
