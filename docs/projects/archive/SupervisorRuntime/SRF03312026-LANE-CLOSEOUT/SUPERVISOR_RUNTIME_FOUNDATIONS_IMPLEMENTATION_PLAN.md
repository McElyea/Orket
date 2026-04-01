# Supervisor Runtime Foundations Implementation Plan
Last updated: 2026-03-31
Status: Completed (archived lane closeout authority)
Owner: Orket Core
Lane type: Supervisor runtime foundations / archived Packet 1 implementation lane

Requirements authority: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`
Closeout authority: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
Contract delta: `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_PACKET1_APPROVAL_SLICE_REALIGNMENT_2026-03-31.md`

## Authority posture

This document is the archived execution authority for the completed SupervisorRuntime Packet 1 lane.

The shipped durable Packet 1 contract surfaces remain active in:
1. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
3. `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`

Before closeout, the approval-checkpoint slice was realigned from the earlier planned governed turn-tool destructive-mutation path to the governed kernel `NEEDS_APPROVAL` lifecycle on the default `session:<session_id>` namespace scope.
That realignment was required because the governed turn-tool path currently truthfully creates approval requests and terminal stop outcomes, but does not provide an approve-to-continue execution path.
The contract delta above records that boundary change.

Future work to add governed turn-tool approval continuation must reopen as a new explicit roadmap lane.

## Closed Packet 1 scope

Packet 1 closed with four bounded behavior families:
1. approval-checkpoint runtime contract
   - selected slice: governed kernel `action.tool_call` proposals whose admission decision is `NEEDS_APPROVAL`
   - canonical operator action path: `POST /v1/approvals/{approval_id}/decision`
   - canonical operator inspection path: `GET /v1/approvals/{approval_id}`
   - explicit runtime continuation path: `POST /v1/kernel/commit-proposal`
   - continuation rule: no resume by implication; Packet 1 does not define a separate resume API for this slice
2. session and context-provider contract
   - selected slice: host-owned interaction `session_id` created at `POST /v1/interactions/sessions`
   - subordinate turn attachment: `POST /v1/interactions/{session_id}/turns`
   - bounded Packet 1 context-provider inputs only
3. operator control surface contract
   - selected slice: approval read model over durable control-plane projection sources
   - fail-closed approve-or-deny action seam only
4. host-owned extension validation contract
   - selected slice: SDK-first manifest family with `manifest_version: v0`
   - canonical validation path: `orket ext validate <extension_root> --strict --json`

## Source authorities at closeout

The lane closed against:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/README.md`
5. `docs/RUNBOOK.md`
6. `docs/API_FRONTEND_CONTRACT.md`
7. the four active Packet 1 specs listed above

## Outcome

Completed in this lane:
1. the four durable Packet 1 specs were extracted from the accepted requirements packet
2. bounded implementation landed for the session boundary, operator approval fail-closed surface, approve-or-deny decision seam, and host-owned extension validation seam
3. the approval-checkpoint slice was truthfully narrowed to the implemented governed kernel approval lifecycle before lane closeout
4. the selected governed runtime slice passed one real-path live proof on the primary path
5. roadmap, docs index, authority docs, and archive closeout were completed in the same change

## Archived historical note

The earlier cold-start candidate named governed turn-tool destructive mutation on the default `issue:<issue_id>` namespace path.
That planning candidate is not shipped Packet 1 truth.
The governed turn-tool path remains live as an approval-request and terminal-stop seam, and the repo continues to preserve that behavior honestly in code and tests.

## Remaining future scope

Outside the completed Packet 1 scope:
1. any approve-to-continue governed turn-tool lifecycle
2. broader session cleanup, retention, or replay infrastructure
3. marketplace, install-source plurality, or cloud extension distribution
4. broader operator-platform work beyond the shipped approval inspection and action surface
