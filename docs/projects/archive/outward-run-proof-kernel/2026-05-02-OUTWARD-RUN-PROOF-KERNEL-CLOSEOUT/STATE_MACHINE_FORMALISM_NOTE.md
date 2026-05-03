# Outward Run Proof Kernel - State Machine Formalism Note

Last updated: 2026-05-01
Status: Archived lane-local planning note - not a durable contract
Owner: Orket Core

Parent closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_IMPLEMENTATION_PLAN.md`

## Purpose

Provide a lightweight formal foundation for outward-run invariants without claiming a full mathematical proof of Orket.

This note uses a labeled transition system to define the outward-run model precisely enough that invariant checker code can be reviewed against it.

## Model Boundary

The model describes serialized evidence only. It does not model:
1. Python runtime correctness,
2. database implementation behavior,
3. model provider semantics,
4. filesystem semantics,
5. wall-clock semantics.

The modeled question is:

```text
Given a sequence of ledger events and authority records, can the verifier derive a well-founded claim about what happened?
```

## Labeled Transition System

Let `E` be a finite sequence of ledger events ordered by the evidence ordering field. Let `A` be authority records. Let `D` be derived records.

Verifier state is:

```text
(S_run, S_proposals, S_effects, S_ledger)
```

Where:
1. `S_run` is one of `initial`, `admitted`, `started`, `turn_open`, `terminal_success`, `terminal_failure`.
2. `S_proposals[approval_id]` is one of `made`, `pending_approval`, `approved`, `denied`, `expired`, `policy_rejected`.
3. `S_effects[approval_id]` is one of `no_effect`, `effect_applied`, `committed`.
4. `S_ledger` is one of `not_checked`, `chain_valid`, `chain_broken`.

Initial state:

```text
(initial, {}, {}, not_checked)
```

## Transitions

| Transition | Precondition | Event | Postcondition |
|---|---|---|---|
| T1 admit_run | `S_run=initial` | `run_submitted` | `S_run=admitted` |
| T2 start_run | `S_run=admitted` | `run_started` | `S_run=started` |
| T3 start_turn | `S_run=started` | `turn_started(T)` | `S_run=turn_open` |
| T4 make_proposal | `S_run=turn_open`, approval id unknown | `proposal_made(A)` | `S_proposals[A]=made`, `S_effects[A]=no_effect` |
| T5 pending_approval | `S_proposals[A]=made` | `proposal_pending_approval(A)` | `S_proposals[A]=pending_approval` |
| T6 approve_proposal | `S_proposals[A]=pending_approval` | `proposal_approved(A)` | `S_proposals[A]=approved` |
| T7 deny_proposal | `S_proposals[A]=pending_approval` | `proposal_denied(A)` | `S_proposals[A]=denied` |
| T8 expire_proposal | `S_proposals[A]=pending_approval` | `proposal_expired(A)` | `S_proposals[A]=expired` |
| T9 policy_reject_proposal | `S_proposals[A]=pending_approval` | `proposal_policy_rejected(A)` | `S_proposals[A]=policy_rejected` |
| T10 invoke_tool | `S_proposals[A]=approved`, `S_effects[A]=no_effect` | `tool_invoked(A)` | `S_effects[A]=effect_applied` |
| T11 record_commitment | `S_effects[A]=effect_applied` | `commitment_recorded(A)` | `S_effects[A]=committed` |
| T12 complete_turn | `S_effects[A]=committed` or terminal no-effect proposal | `turn_completed(T)` | `S_run=started` |
| T13 complete_run_success | `S_run=started`, all invoked effects committed or terminally stopped, terminal status aligns | `run_completed(success)` | `S_run=terminal_success` |
| T14 complete_run_failure | `S_run=started` or `S_run=turn_open` | `run_completed(non-success)` | `S_run=terminal_failure` |

## Forbidden Transitions

| Forbidden transition | Corresponding invariant |
|---|---|
| tool invocation before admission | ORP-INV-001 |
| tool invocation before approval | ORP-INV-002 |
| tool invocation after denial, expiry, or policy rejection | ORP-INV-013 / ORP-INV-014 |
| success with an uncommitted invoked effect or status drift | ORP-INV-003 / ORP-INV-010 / ORP-INV-011 |
| terminal success without final truth | ORP-INV-003 |
| absence claim over a partial ledger view | ORP-INV-022 |

## Reachability Notes

R1: If the verifier reaches `terminal_success`, then admission fired, run and turn start events are ordered, approval fired before every effect, every invoked effect was committed, terminal truth fired exactly once, and terminal status aligned across run authority and ledger evidence.

R2: If a proposal is denied, expired, or policy rejected, then no effect for that approval id is reachable in a valid state.

R3: Event ordering induces a deterministic verifier transition sequence. The verifier should have no hidden nondeterminism.

These are inspection-level reachability arguments, not machine-checked proofs.

## Implementation Use

The checker should be structured so reviewers can map code blocks to T1 through T14 and the forbidden transitions. This is not a proof, but it reduces authority drift between the docs and checker.

## Honest Limitations

1. Python implementation bugs are outside the model.
2. A compromised bundle emitter can still create bad evidence.
3. Ledger integrity is checked by packaged `ledger_export.v1` bytes and hash evidence, not proven by this LTS.
4. Model output semantics remain uninterpreted.

## Path Toward Stronger Guarantees

1. Correspondence comments in checker code are immediately feasible.
2. Property-based tests with generated event sequences are near-term feasible if dependency policy allows `hypothesis`.
3. Alloy modeling is a future lane.
4. Coq or Lean proof is a future lane.
