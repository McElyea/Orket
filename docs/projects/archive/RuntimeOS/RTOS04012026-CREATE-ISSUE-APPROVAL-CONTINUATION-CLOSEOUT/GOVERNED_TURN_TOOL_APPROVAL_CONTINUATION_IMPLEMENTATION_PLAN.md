# RuntimeOS Governed Turn-Tool Approval Continuation Implementation Plan
Last updated: 2026-04-01
Status: Completed and archived
Owner: Orket Core
Lane type: RuntimeOS / governed turn-tool approval continuation

Paired requirements authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_REQUIREMENTS.md`

Durable contract authority:
1. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`

Related authority:
1. `docs/API_FRONTEND_CONTRACT.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/RUNBOOK.md`
4. `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_CREATE_ISSUE_APPROVAL_CONTINUATION_2026-04-01.md`

## Outcome

This bounded lane is complete.

Shipped lane facts:
1. the selected additional capability class beyond the shipped `write_file` slice is `create_issue`
2. one governed turn-tool `create_issue` request creates `request_type=tool_approval` with `reason=approval_required_tool:create_issue` on the default `issue:<issue_id>` path
3. the existing approval list, detail, and decision surfaces remain the operator inspection and decision path
4. approval now triggers one runtime-owned same-governed-run continuation on the already-selected `control_plane_target_ref`
5. denial now terminal-stops that same governed turn-tool run
6. continuation fails closed on target-run identity drift and namespace drift
7. no new operator-visible resume API, no broader approval-required tool family, and no broader namespace scope shipped on this lane

## Completion Gate Disposition

1. exact additional capability-class selection: satisfied by `create_issue`
2. request creation: satisfied
3. inspect and approve-or-deny on existing surfaces: satisfied
4. same-governed-run continuation on approval: satisfied
5. same-governed-run explicit stop on denial: satisfied
6. fail-closed target or namespace drift handling: satisfied
7. bounded one-tool / one-scope / no-general-resume posture: satisfied

## Proof Entrypoints

1. `python -m pytest -q tests/application/test_turn_executor_middleware.py -k "approval_resume_continues_same_governed_run or approval_required_tool"`
2. `python -m pytest -q tests/application/test_engine_approvals.py`
3. `python -m pytest -q tests/application/test_turn_tool_dispatcher.py`
4. `python -m pytest -q tests/application/test_orchestrator_epic.py -k "pending_gate_callback_creates_tool_approval_request or pending_gate_callback_creates_create_issue_tool_approval_request"`
5. `python -m pytest -q tests/interfaces/test_api_approvals.py tests/interfaces/test_api_approval_projection_fail_closed.py`
