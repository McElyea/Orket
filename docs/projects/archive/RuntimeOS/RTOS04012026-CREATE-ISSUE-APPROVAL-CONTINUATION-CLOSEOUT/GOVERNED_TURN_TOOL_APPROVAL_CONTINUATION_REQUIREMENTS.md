# RuntimeOS Governed Turn-Tool Approval Continuation Requirements
Last updated: 2026-04-01
Status: Completed and archived
Owner: Orket Core
Lane type: RuntimeOS / governed turn-tool approval continuation requirements

Archived implementation authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_IMPLEMENTATION_PLAN.md`

Durable contract authority:
1. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`

Related authority:
1. `docs/API_FRONTEND_CONTRACT.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/RUNBOOK.md`
4. `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_CREATE_ISSUE_APPROVAL_CONTINUATION_2026-04-01.md`

## Outcome

This scoped requirements companion is complete.

Shipped lane facts:
1. the selected additional governed turn-tool approval-required capability class is `create_issue`
2. the admitted request family remains `tool_approval` with `reason=approval_required_tool:create_issue`
3. the admitted namespace scope remains the default `issue:<issue_id>` path and the existing `control_plane_target_ref`
4. approve continues the same governed turn-tool run and deny terminal-stops that same governed turn-tool run
5. no broader approval-required tool family, broader namespace scope, or manual resume API was admitted

## Requirements Gate Disposition

1. GTAC-01 one additional capability-class selection: satisfied by the bounded `create_issue` slice
2. GTAC-02 explicit continuation lifecycle: satisfied
3. GTAC-03 fail-closed continuation preconditions: satisfied
4. GTAC-04 proof expectation: satisfied
5. GTAC-05 same-change update targets: satisfied
