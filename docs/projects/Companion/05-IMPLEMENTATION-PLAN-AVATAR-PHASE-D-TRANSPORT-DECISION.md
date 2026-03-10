# Companion Avatar Phase D Implementation Plan (Transport Decision Gate)

Last updated: 2026-03-09
Status: Draft (queued)
Owner: Orket Core
Canonical lane plan: `docs/projects/Companion/01-AVATAR-POST-MVP-CANONICAL-IMPLEMENTATION-PLAN.md`
Contract authority: `docs/specs/COMPANION_AVATAR_POST_MVP_CONTRACT.md`
Depends on: Phase B minimum, Phase C recommended

## 1. Objective

Decide whether to keep the current transport path or escalate to WebRTC based on measured evidence, not assumptions.

## 2. Scope Deliverables

1. Reference hardware profile declaration for measurement.
2. Repeatable benchmark procedure for idle and speaking runs.
3. Performance budget report against lane ceilings.
4. Degradation trigger/behavior evidence.
5. Decision record:
   1. keep current transport, or
   2. open scoped WebRTC implementation lane.

## 3. Detailed Tasks

### Workstream D1 - Measurement Harness and Baseline
Tasks:
1. Declare reference mid-tier hardware profile and measurement tooling.
2. Capture avatar-disabled baseline TTI and resource profile.
3. Capture avatar-enabled idle and speaking runs (60s each).

Acceptance:
1. measurement inputs and methods are reproducible.
2. baseline and avatar-enabled runs are comparable.

### Workstream D2 - Budget Evaluation and Degradation Behavior
Tasks:
1. Evaluate FPS, TTI delta, and CPU/GPU uplift against lane budgets.
2. Validate degradation order under induced resource pressure.
3. Confirm degraded mode preserves chat/voice/settings usability.

Acceptance:
1. pass/fail is explicit per budget dimension.
2. degradation sequence behavior is evidenced.

### Workstream D3 - Decision Record
Tasks:
1. Publish decision memo with measured evidence.
2. If transport upgrade is justified, define scoped follow-on plan with rollback constraints.
3. If not justified, document retain-current rationale and next review trigger.

Acceptance:
1. decision is evidence-backed and auditable.
2. no speculative migration work starts without gate approval.

## 4. Verification Plan

Integration:
1. measured idle/speaking runs with avatar enabled.
2. degraded-mode behavior verification under pressure.

Live:
1. end-to-end local Companion usage session with avatar enabled under reference profile.
2. stability check over sustained chat + voice usage window.

## 5. Completion Gate

Phase D is complete when:
1. budgets are measured and compared to contract thresholds,
2. degradation behavior is validated with preserved core usability,
3. transport decision is published with explicit rationale and next-step scope.
