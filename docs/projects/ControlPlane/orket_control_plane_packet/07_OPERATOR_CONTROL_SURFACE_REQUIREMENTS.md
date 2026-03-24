# Operator Control Surface Requirements
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation / operator plane

## Purpose

Define the minimum bounded operator control surface required for an OS-grade governed workload runtime.

## Authority note

Operator input and command enums are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

## Core assertion

Operator control must be:
1. explicit
2. auditable
3. bounded by policy
4. distinct from runtime autonomy
5. strong enough to unblock or terminate unsafe situations

This is a contract, not a UI design.

## Inspection intents

### OP-01. Inspection surface

The control plane must support inspection of at minimum:
1. run state
2. current and prior attempts
3. failure classifications
4. recovery decisions
5. reservations, leases, and owned resources
6. reconciliation records
7. residual uncertainty
8. final closure status

## Operator input split

### OP-02. Operator commands

The control plane must support operator commands at minimum for:
1. `approve_continue`
2. `approve_degraded_continue`
3. `force_reconcile`
4. `quarantine_run`
5. `cancel_run`
6. `release_or_revoke_lease`
7. `approve_cleanup`
8. `mark_terminal`

### OP-03. Operator risk acceptance

Operator risk acceptance is:
1. explicit authorization to continue despite bounded unresolved uncertainty
2. a continuation input, not evidence of world state
3. subject to policy and scope restrictions

### OP-04. Operator attestation

Operator attestation is:
1. bounded human assertion for a policy-allowed scope
2. recorded separately from command and risk acceptance
3. labeled as attested rather than observed
4. never equivalent to adapter observation

## Authority boundaries

### OP-05. Operator-only actions

Certain actions must be expressible as operator-only under policy, including at minimum:
1. override continuation after unresolved uncertainty
2. cleanup requiring human judgment
3. continuation after repeated contradiction or quarantine
4. destructive actions requiring human review

### OP-06. Runtime does not impersonate operator

The runtime must never fabricate or simulate an operator decision.
Absence of an operator action must remain visible as absence.

## Command validation

### OP-07. Preconditions

An operator command must be validated against:
1. current run state
2. current reservations, leases, and resources
3. policy constraints
4. unresolved reconciliation requirements
5. target object identity
6. command-specific preconditions

### OP-08. Command rejection

Invalid operator commands must:
1. be rejected
2. preserve prior state
3. emit a structured rejection receipt
4. avoid hidden fallback behavior

## Truth boundary

### OP-09. Terminal commands do not rewrite truth

`mark_terminal` may:
1. stop continuation
2. force terminal closure
3. affect terminality basis

`mark_terminal` may not:
1. rewrite result class
2. convert insufficient evidence into sufficient evidence
3. erase residual uncertainty

## Auditability

### OP-10. Operator action receipts

Every operator action must produce durable machine-readable evidence of:
1. who acted
2. which operator input class was used
3. what was targeted
4. which command or attestation was issued
5. under what preconditions
6. what changed
7. what remained blocked or uncertain

## Interaction with recovery and lifecycle

### OP-11. Operator unblocks are explicit transitions

Any transition from `operator_blocked` or `quarantined` due to human intervention must reference the operator action receipt.

### OP-12. Operator visibility into degraded modes

If execution continues in degraded mode, the operator-visible state must reflect:
1. which degraded mode
2. why it was selected
3. which capabilities are now blocked

## Acceptance criteria

This draft is acceptable only when:
1. operator power is real but bounded
2. the runtime cannot smuggle implicit human approval
3. commands, risk acceptance, and attestation remain distinct
4. `mark_terminal` can affect terminality without rewriting truth
5. inspection surfaces align with the foundation object model
