# Contract Delta: SupervisorRuntime write_file approval continuation

Last updated: 2026-04-01

## Metadata
- Change title: SupervisorRuntime bounded turn-tool `write_file` approval continuation closeout
- Date: 2026-04-01
- Owners: Orket Core
- Related roadmap authority:
  - `docs/projects/archive/RuntimeOS/RTOS04012026-WRITE-FILE-APPROVAL-CONTINUATION-CLOSEOUT/WRITE_FILE_APPROVAL_CONTINUATION_IMPLEMENTATION_PLAN.md`

## Summary

The durable approval-checkpoint contract previously selected only the governed kernel `NEEDS_APPROVAL` lifecycle as a shipped approve-to-continue slice.

This delta adds one more shipped bounded slice only:
1. governed turn-tool `write_file`
2. default `issue:<issue_id>` namespace scope only
3. existing `tool_approval` plus `approval_required_tool:write_file` request shape only
4. existing `control_plane_target_ref` only
5. one runtime-owned same-governed-run continue-or-stop outcome only

## Before

Before this change:
1. governed turn-tool approval-required requests were operator-visible request-and-stop seams only
2. approving a `write_file` request did not continue the same governed turn-tool run
3. denying a `write_file` request did not terminal-close that same governed turn-tool run
4. the durable approval spec and authority docs still described all turn-tool approval-required rows as outside the shipped approve-to-continue contract

## After

After this change:
1. approving the admitted turn-tool `write_file` slice triggers one runtime-owned same-governed-run continuation by consuming the accepted pre-effect same-attempt checkpoint on the already-selected governed run
2. denying that admitted slice terminal-stops the same governed turn-tool run
3. the bounded slice fails closed on target-run identity drift and namespace drift
4. no new operator-visible resume API, no broader approval-required tool family, and no broader namespace scope were added

## Required same-change updates

1. update `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
2. update `CURRENT_AUTHORITY.md`
3. update `docs/API_FRONTEND_CONTRACT.md`
4. update `docs/RUNBOOK.md`
5. archive the completed RuntimeOS bounded lane and remove the active roadmap entry

## Verification notes

Primary proof for the bounded slice:
1. `python -m pytest -q tests/application/test_turn_executor_middleware.py -k "write_file_approval_resume_continues_same_governed_run"`
2. `python -m pytest -q tests/application/test_engine_approvals.py`
3. `python -m pytest -q tests/interfaces/test_api_approvals.py tests/interfaces/test_api_approval_projection_fail_closed.py`
