# Orket NorthStar Governed Change Packets Requirements v1

Last updated: 2026-04-19
Status: Accepted requirements - archived with completed implementation lane
Owner: Orket Core

Implementation plan: `docs/projects/archive/northstar-governed-change-packets/NGCP04192026-LANE-CLOSEOUT/ORKET_NORTHSTAR_GOVERNED_CHANGE_PACKETS_IMPLEMENTATION_PLAN.md`

## Purpose

Define the end-to-end NorthStar work required to grow Orket from one closed governed repo-change packet into a repeatable governed-change product path.

This was the accepted requirements companion for the completed implementation lane.

## Revision Posture

Reopened on 2026-04-19 by explicit user request for requirements revision.

Accepted for implementation planning on 2026-04-19 by explicit user request to create the implementation plan.

Completed execution authority is archived with the implementation plan.

## NorthStar Statement

The product north star is:

```text
Make governed changes independently verifiable before making them broader.
```

The operator-facing target is:

```text
Given a governed change packet, a skeptical outside operator can verify in
minutes that the change was authorized, bounded, validator-backed,
effect-lined, uniquely finalized, and claim-capped without trusting Orket first.
```

## Current Baseline

The first closed slice is `trusted_repo_config_change_v1`.

Current authority snapshot:

1. `CURRENT_AUTHORITY.md`

Current durable authority:

1. `docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md`
2. `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`
3. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`
4. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
5. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`

Current guide and reference surfaces:

1. `docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md`

Closeout and archive references:

1. `docs/projects/archive/governed-change-packet/GCP04192026-LANE-CLOSEOUT/CLOSEOUT.md`

Current truthful limits:

1. the admitted packet is fixture-bounded
2. current claim ceiling is `verdict_deterministic`
3. replay determinism is not proven
4. text determinism is not proven
5. provider-backed governed-proof paths are not yet externally admitted
6. the adversarial benchmark is staged, not published

## Scope

This accepted requirements lane covers the next end-to-end NorthStar expansion after the first packet closeout.

It may include:

1. making packet generation easier for outside operators
2. hardening the standalone verifier as the primary trust surface
3. adding one next admitted packet family only after requirements acceptance
4. publishing or replacing the staged adversarial benchmark after explicit approval
5. defining a product adoption path around independently verifiable governed changes

It must not include:

1. broadening public trust claims without same-change evidence
2. treating logs, approvals, dashboards, or summaries as proof authority
3. adding multiple packet families before one next family is admitted and verified
4. claiming replay or text determinism without new proof artifacts
5. treating provider-backed demos as public trust evidence while quota or runtime proof remains blocked

## Requirements

NS-GCP-001: NorthStar work MUST preserve the packet as an entry artifact over authority-bearing evidence, not a substitute authority surface.

NS-GCP-002: Every claim-bearing packet path MUST have a standalone verifier outcome that can cap or reject claims without hidden runtime state.

NS-GCP-003: Every new packet family MUST define its compare scope, operator surface, authority artifacts, validators, claim ceiling, and unsupported claims before implementation starts.

NS-GCP-004: Every new packet family MUST include at least one positive packet and at least one negative or adversarial proof family.

NS-GCP-005: Public or adoption-facing language MUST stay bounded to the strongest independently checkable claim tier.

NS-GCP-006: Any broadened trust boundary MUST update the relevant durable specs and contract delta in the same change.

NS-GCP-007: Packet verifier proof MUST include non-interference evidence and at least one fail-closed malformed-packet case.

NS-GCP-008: Operator guidance MUST distinguish authority-bearing artifacts from support-only projections.

NS-GCP-009: Benchmark promotion MUST follow staging and publication rules and must not publish staged artifacts without explicit approval.

NS-GCP-010: Follow-on implementation MUST prefer the smallest next packet family that improves independent verification over adding broad runtime surface area.

## Candidate Phase Envelope

### Phase 1 - Requirements Acceptance

Goal: turn this active draft into accepted requirements for exactly one next bounded NorthStar increment.

Required decisions:

1. whether the next increment is productization of `trusted_repo_config_change_v1` or a new packet family
2. whether the staged adversarial benchmark should be published, replaced, or kept staged
3. what claim ceiling the next increment is allowed to target
4. which verifier usability gaps block outside-operator adoption

Exit criteria:

1. accepted requirements name one next bounded scope
2. unsupported claims remain explicit
3. roadmap reopen trigger is clear

### Phase 2 - Packet Productization

Candidate goal: make the first packet easier to run, inspect, and trust without changing its claim ceiling.

Candidate outputs:

1. a shorter outside-operator command path
2. verifier output that is easier to audit
3. clearer packet manifest and authority-row diagnostics
4. packaging guidance that avoids requiring the full developer workflow

Exit criteria:

1. an outside operator can generate and verify the packet without reconstructing internal context
2. verifier output still fails closed on missing, contradictory, or overclaiming packets
3. no stronger public trust claim is introduced without proof

### Phase 3 - Next Packet Family Admission

Candidate goal: admit one additional governed-change packet family only if it can be verified at least as clearly as the repo-change packet.

Candidate families must be evaluated against:

1. local reproducibility
2. authority evidence completeness
3. validator determinism
4. negative proof clarity
5. external evaluator legibility
6. provider or environment dependency risk

Exit criteria:

1. one family is admitted or all candidates are rejected with reasons
2. durable specs are updated for any admitted family
3. the standalone verifier caps claims for that family

### Phase 4 - Benchmark Publication Decision

Candidate goal: decide whether to publish the adversarial packet benchmark or keep it staged.

Required proof:

1. staged benchmark artifact is current
2. benchmark catches all frozen failure classes
3. public wording is limited to the verified corpus
4. publication approval is explicit

Exit criteria:

1. benchmark is either published through the accepted process or remains staged with stated blockers
2. benchmark claims do not exceed verifier evidence

### Phase 5 - Adoption Surface

Candidate goal: explain why Orket is worth choosing using packet evidence rather than rhetoric.

Required surface:

1. a short operator runbook
2. a comparative trust case against `workflow + logs + approvals`
3. a statement of what Orket proves and what it does not prove
4. a repeatable path for the next admitted packet family

Exit criteria:

1. adoption wording remains claim-capped
2. the verifier, not Orket narration, determines the strongest claim
3. future expansion is queued as a new explicit lane instead of hidden backlog

## Acceptance Criteria

This requirements lane moved to implementation planning on 2026-04-19 with this bounded scope:

1. next bounded scope: productize the existing `trusted_repo_config_change_v1` governed change packet
2. implementation outputs are limited to operator usability, verifier auditability, staged benchmark freshness, and adoption material for that scope
3. no second packet family is admitted in this first implementation increment
4. no publication action is approved by these requirements alone

Any later implementation increment that admits a second packet family, targets replay determinism, targets text determinism, or publishes a benchmark requires a revised requirement or same-change implementation-plan update.

## Reopen Trigger

Requirements revision is closed for the first implementation increment.

Reopen these requirements only when the user explicitly asks to revise, supersede, or retire this NorthStar requirements lane.

## Remaining Open Questions

1. Should the next NorthStar increment productize the existing repo-change packet or admit a second packet family?
2. Should the adversarial benchmark be published after review or kept staged until another packet family exists?
3. What is the minimum packaging surface that lets an outside operator run the verifier without the full Orket dev workflow?
4. Which future claim, if any, should be targeted first: replay determinism, text determinism, broader packet family support, or verifier auditability?
