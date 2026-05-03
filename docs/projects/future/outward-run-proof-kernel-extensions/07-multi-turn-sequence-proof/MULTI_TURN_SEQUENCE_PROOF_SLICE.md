# Slice 07 - Multi-Turn Sequence Proof Extension

Last updated: 2026-05-02
Status: Deferred slice plan
Owner: Orket Core

Parent future lane: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`
Base archive: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`

## Purpose

Extend the outward-run proof kernel to cover `governed_tool_sequence` runs after the single-turn proof kernel is working.

## Deferred Precondition

Slices 01 through 06 must meet their single-turn exit criteria before this slice can close. This slice may inform schema design now, but it must not block the first proof kernel.

## Scope

In scope:
1. finite `governed_tool_sequence` runs with two or more turns
2. turn ordering across the full event sequence
3. cross-turn model evidence linkage
4. optional witness bundle extension for sequence evidence
5. corruption families specific to multi-turn ordering

Out of scope:
1. unbounded turn sequences
2. semantic proof that the model used prior results correctly
3. single-turn approval path closure

## New Invariants

These extend Slice 03 and activate only for bundles whose `run_authority.acceptance_contract_sequence` is present.

| ID | Invariant | Failure Code |
|---|---|---|
| ORP-INV-015 | For each turn index `T`, turn-local events must appear in order: `turn_started`, `proposal_made`, `proposal_pending_approval`, `proposal_approved`, `tool_invoked`, `commitment_recorded`, `turn_completed`. | `multi_turn_sequence_ordering_violated` |
| ORP-INV-017 | `turn_completed(T)` must precede `turn_started(T+1)` for all nonterminal sequence turns. | `multi_turn_interleaving_violated` |
| ORP-INV-018 | Turn `T` model evidence must reference a prior-results digest matching connector results from turns `0..T-1`. | `cross_turn_result_linkage_missing` |
| ORP-INV-019 | Tool at turn `T` must match the `T`th declared tool in `acceptance_contract_sequence`. | `sequence_tool_order_violated` |
| ORP-INV-020 | A completed sequence must have exactly `N` `tool_invoked` events for declared sequence length `N`, unless terminal denial, expiry, or policy rejection occurred. | `sequence_length_violated` |

## Bundle Extension Draft

```json
{
  "multi_turn_sequence": {
    "declared_length": 2,
    "turns": [
      {
        "turn_index": 0,
        "tool_name": "<string>",
        "prior_governed_results_digest": null,
        "model_invocation_evidence_index": 0,
        "approval_authority_index": 0,
        "effect_evidence_index": 0
      },
      {
        "turn_index": 1,
        "tool_name": "<string>",
        "prior_governed_results_digest": "<sha256 hex>",
        "model_invocation_evidence_index": 1,
        "approval_authority_index": 1,
        "effect_evidence_index": 1
      }
    ]
  }
}
```

## Cross-Turn Result Linkage Protocol

1. After each `commitment_recorded(T)`, serialize the connector result canonically and record `committed_result_digest(T)`.
2. Before model call `T+1`, compute `prior_results_digest = sha256(canonical([committed_result_digest(0), ..., committed_result_digest(T)]))`.
3. Carry `prior_results_digest` in the witness package for turn `T+1`.
4. The verifier recomputes the digest from committed results in the package.

This proves the prior results were carried into the next prompt boundary as recorded evidence. It does not prove the model reasoned correctly from them.

## New Corruption Families

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-090 | base_multi_turn_approved | set second turn index equal to first turn index | `multi_turn_sequence_ordering_violated` | ORP-INV-015 |
| ORP-CORR-091 | base_multi_turn_approved | insert `turn_started(1)` before `turn_completed(0)` | `multi_turn_interleaving_violated` | ORP-INV-017 |
| ORP-CORR-092 | base_multi_turn_approved | change turn 1 prior-results digest | `cross_turn_result_linkage_missing` | ORP-INV-018 |
| ORP-CORR-093 | base_multi_turn_approved | swap declared sequence tool order | `sequence_tool_order_violated` | ORP-INV-019 |
| ORP-CORR-094 | base_multi_turn_approved | remove all events for turn 1 | `sequence_length_violated` | ORP-INV-020 |

## Exit Criteria

1. a two-turn `governed_tool_sequence` run emits a valid witness package
2. ORP-INV-015 through ORP-INV-020 pass for valid evidence
3. ORP-CORR-090 through ORP-CORR-094 produce expected failure codes
4. the assurance case index includes multi-turn claims
5. single-turn proof kernel exit criteria remain green
