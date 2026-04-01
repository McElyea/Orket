# Contract Delta: SupervisorRuntime Packet 1 Approval Slice Realignment

## Summary
- Change title: SupervisorRuntime Packet 1 approval slice realignment to governed kernel `NEEDS_APPROVAL`
- Owner: Orket Core
- Date: 2026-03-31
- Affected contract(s):
  - `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
  - `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`
  - `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`
  - `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_IMPLEMENTATION_PLAN.md`

## Delta
- Current behavior:
  - the previously accepted Packet 1 planning candidate named governed turn-tool destructive mutation on the default `issue:<issue_id>` namespace path as the selected approval-checkpoint slice
  - the governed turn-tool path truthfully creates approval requests and terminal stop outcomes when approval is required
  - the governed turn-tool path does not currently provide a production approve-to-continue execution path after operator approval
  - the governed kernel `NEEDS_APPROVAL` path already provides a bounded end-to-end admit -> inspect -> approve or deny -> commit or stop lifecycle with durable control-plane projection and live proof
- Proposed behavior:
  - close SupervisorRuntime Packet 1 on the governed kernel `NEEDS_APPROVAL` approval lifecycle under the default `session:<session_id>` namespace scope
  - keep `/v1/approvals/{approval_id}` and `/v1/approvals/{approval_id}/decision` as the canonical Packet 1 operator inspection and action surfaces
  - treat governed turn-tool approval-required requests as operator-visible request/stop seams only, not as the shipped Packet 1 approve-to-continue contract
- Why this break is required now:
  - the old turn-tool selection would have claimed a continuation contract that is not implemented end to end
  - narrowing to the implemented kernel slice preserves truthful verification and allows the lane to close without inventing authority

## Migration Plan
1. Compatibility window:
   - none; this is a same-change contract realignment before lane closeout, not a staged compatibility period
2. Migration steps:
   - realign the archived requirements and implementation lane docs
   - update the active approval and operator specs to the governed kernel Packet 1 slice
   - sync `CURRENT_AUTHORITY.md`, `docs/RUNBOOK.md`, `docs/API_FRONTEND_CONTRACT.md`, `docs/ROADMAP.md`, and `docs/README.md`
   - archive the lane and record closeout proof
3. Validation gates:
   - `ORKET_DISABLE_SANDBOX=1 python scripts/nervous_system/run_nervous_system_live_evidence.py`
   - `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_nervous_system_live_evidence.py`
   - approval/operator/kernel integration proof
   - docs hygiene proof

## Rollback Plan
1. Rollback trigger:
   - governed kernel approval live proof or operator-surface proof fails after the contract realignment
2. Rollback steps:
   - reopen the SupervisorRuntime lane instead of archiving it
   - restore the approval slice to an unresolved planning posture and keep the real-path live proof gate open
3. Data/state recovery notes:
   - no data migration is involved; this delta changes contract authority, not stored runtime records

## Versioning Decision
- Version bump type: none
- Effective version/date: 2026-03-31
- Downstream impact:
  - approval consumers must treat the completed Packet 1 approve-to-continue lifecycle as the governed kernel slice only
  - future governed turn-tool approval continuation requires a new explicit contract and roadmap lane
