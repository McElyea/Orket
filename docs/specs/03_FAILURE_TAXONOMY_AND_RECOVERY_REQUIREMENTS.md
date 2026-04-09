# Failure Taxonomy and Recovery Requirements
Last updated: 2026-04-09
Status: Active durable spec authority
Owner: Orket Core
Lane type: Control-plane foundation / recovery

## Purpose

Define the minimum failure taxonomy and recovery rules required for Orket to recover truthful execution without allowing narrative, hidden heuristics, or unsafe retries to substitute for authority.

## Authority note

Failure-plane, failure-class, side-effect boundary, and recovery action enums are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

This document defines how those classes drive recovery behavior.

## Core assertion

Orket does not recover a model.
Orket recovers governed execution in the presence of untrusted proposals, execution defects, and truth uncertainty.

## Failure planes

### FR-01. Primary failure plane is mandatory

Every failure must carry:
1. one primary failure plane from the glossary
2. one or more failure classes where applicable
3. one side-effect boundary classification if execution or interruption occurred

## Side-effect boundary classification

### FR-02. Side-effect boundary classes are mandatory

Every failed or interrupted attempt must be classified as:
1. `pre_effect_failure`
2. `effect_boundary_uncertain`
3. `post_effect_observed`

Where the runtime cannot determine effect status truthfully, it must publish uncertainty explicitly rather than downgrading to `pre_effect_failure` by convenience.

## Recovery authority

### FR-03. Recovery authorization

Recovery may be authorized only by the supervisor under resolved policy.

A model, adapter, or workload-specific component may propose a recovery candidate but may not authorize it.

### FR-04. Recovery decision basis

Recovery authorization must be based on:
1. primary and secondary failure classifications
2. side-effect boundary classification
3. capability and effect class
4. reservation, lease, and resource ownership state
5. checkpoint validity
6. reconciliation results where required
7. operator actions where required

## Allowed recovery actions

### FR-05. Minimum recovery action vocabulary

The control plane must support at minimum the following recovery actions:
1. `retry_same_attempt_scope`
2. `start_new_attempt`
3. `resume_from_checkpoint`
4. `require_observation_then_continue`
5. `require_reconciliation_then_decide`
6. `perform_control_plane_recovery_action`
7. `downgrade_to_degraded_mode`
8. `quarantine_run`
9. `escalate_to_operator`
10. `terminate_run`

If a recovery action authorizes continued workload execution, the recovery decision must declare whether it:
1. resumes an existing attempt
2. starts a new attempt

### FR-06. Forbidden recovery action

The runtime must not support a recovery action whose only basis is "ask the model to explain what happened" or equivalent narrative substitution.

## Recovery eligibility rules

### FR-07. Pre-effect retry

Automatic retry may be allowed for `pre_effect_failure` only when:
1. policy allows retry
2. capability class permits it
3. reservation, lease, and resource state are still valid
4. no unresolved contradiction exists
5. retry budget is not exhausted

### FR-08. Effect-boundary uncertain handling

For `effect_boundary_uncertain`, blind retry is prohibited unless the relevant capability and effect class explicitly declares it safe under idempotency guarantees.

Otherwise the required next step is:
1. reconciliation
2. operator gate
3. terminal stop

### FR-09. Post-effect observed failure

For `post_effect_observed`, the supervisor must choose among:
1. proceed if the effect truthfully satisfied the step despite surrounding failure
2. reconcile before continuation
3. compensate if supported and authorized
4. escalate
5. terminate

### FR-10. Contradiction persistence

Repeated contradiction across attempts must not produce infinite retry.
Policy must permit only:
1. degradation
2. quarantine
3. operator escalation
4. termination

## Truth repair rules

### FR-11. Truth repair by evidence

Truth repair must use:
1. receipts
2. effect journal entries
3. validated artifacts
4. reservation and lease state
5. authoritative adapter observations
6. reconciliation outputs

Truth repair must not use:
1. narrative explanations as evidence
2. inferred side effects with no receipt or observation
3. model confidence statements
4. operator risk acceptance as evidence of world state

### FR-12. Unsupported claim handling

When an unsupported claim occurs:
1. the claim must be rejected as authority
2. the contradiction or evidence gap must be recorded
3. final truth surfaces must not carry the unsupported claim forward
4. recovery must require observation or constrained restatement where applicable

### FR-13. False completion handling

A false completion claim is control-plane significant.
If a model claims completion and authoritative evidence does not support completion:
1. the run must not close as complete
2. the claim must be recorded
3. the next action must be gated through recovery
4. repeated occurrence may trigger quarantine

## Recovery receipts

### FR-14. Recovery receipt requirements

Each recovery decision must publish durable evidence of:
1. failed attempt reference
2. failure classifications
3. side-effect boundary class
4. reservation, lease, and resource considerations
5. checkpoint considerations
6. reconciliation requirement decision
7. authorized action
8. blocked actions
9. operator requirement if any
10. rationale basis

## Degraded modes

### FR-15. Required degraded-mode classes

The control plane must at minimum support the concept of:
1. observe-only
2. extractive-only
3. no-mutation
4. single-step continuation
5. operator-confirmed continuation only

The exact degraded modes supported by a workload may be a subset, but the vocabulary must exist.

## Terminal requirements

### FR-16. Honest non-completion

Where recovery cannot truthfully and safely proceed, the run must terminate or remain operator-blocked with an explicit non-completion surface.
Silent downgrade into ambiguous success is prohibited.

## Acceptance criteria

This draft is acceptable only when:
1. failure classes meaningfully change recovery policy
2. effect uncertainty cannot be bypassed by convenience
3. false completion and unsupported claims are treated as first-class defects
4. degraded modes exist as real control-plane outputs
5. recovery receipts explain why the chosen path was legal
6. final truth surfaces remain aligned with authoritative evidence after recovery
