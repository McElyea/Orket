# Outward Run Invariants v1

Last updated: 2026-05-02
Status: Active durable contract for the approved single-turn outward proof kernel
Owner: Orket Core

Originating closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`
Slice authority: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/03-invariant-checker/INVARIANT_CHECKER_SLICE.md`
Deferred extensions: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

This invariant contract is active for the `outward_run_write_file_approved_v1` single-turn approved path. Denial, policy-rejection, out-of-scope, multi-turn, ODR, and public-trust extensions remain outside this active boundary until their package fixtures and same-change authority updates exist.

## Purpose

Define the bounded invariant model for admitted outward-run witness packages.

The intended theorem shape is:

```text
If the side-effect-free verifier accepts an outward_run_witness_package.v1 for
an admitted outward-run compare scope, then the serialized package evidence
satisfies the matching Outward Run Invariants v1 model.
```

This is not a formal proof of Orket, Python, model output semantics, filesystem behavior, database behavior, or every API path.

## Relationship to Trusted Run Invariants v1

This spec depends on `docs/specs/TRUSTED_RUN_WITNESS_V1.md` and `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` for shared proof vocabulary. It adds an outward-pipeline-specific invariant model without modifying the trusted-run model.

The `ORP-INV-*` ids are outward-pipeline-local and do not collide with `TRI-INV-*`, `TRC-INV-*`, or `TTPD-INV-*`.

## Initial Model Scope

| Field | Value |
|---|---|
| Compare scope | `outward_run_write_file_approved_v1` |
| Bundle schema | `outward_run.witness_bundle.v1` |
| Operator surface | `outward_run_witness_report.v1` |
| Governed tool | `write_file` |
| Approval path | single human approval |
| Effect | one file write |

Multi-turn sequence and ODR determinism extensions are deferred and must not block the single-turn model.

## Invariant Table

| ID | Activation | Invariant | Failure Code |
|---|---|---|---|
| ORP-INV-001 | single-turn core | `run_submitted` must appear before any `tool_invoked` event. | `effect_before_admission` |
| ORP-INV-002 | single-turn core | `proposal_approved` for a governed tool must appear before corresponding `tool_invoked`. | `effect_before_approval` |
| ORP-INV-003 | single-turn core | Terminal success requires exactly one terminal run event, success-class status alignment across run authority and ledger evidence, and no unresolved invoked effect without commitment. | `final_truth_missing`, `terminal_status_drift`, or `commitment_missing_after_effect` |
| ORP-INV-004 | single-turn core | Effect claims require a `tool_invoked` ledger event for the named tool and run. | `effect_evidence_missing` |
| ORP-INV-005 | single-turn core | Projection-only fields and digest-only commitments must not substitute for authority bytes or verified ledger anchors. | `projection_substituted_for_authority` or `source_bytes_missing_for_digest` |
| ORP-INV-006 | single-turn core | Full-ledger claims must verify from packaged `ledger_export.v1` payload bytes using `LEDGER_EXPORT_V1`; partial views cannot claim completeness. | `ledger_export_missing`, `ledger_export_digest_mismatch`, `ledger_payload_bytes_missing`, `ledger_chain_broken`, or `ledger_chain_hash_mismatch` |
| ORP-INV-007 | single-turn core | Requested outward posture must not exceed the evidence-supported ceiling. | `claim_tier_not_supported` |
| ORP-INV-008 | single-turn core | `proposal_made` must precede `proposal_pending_approval` for the same approval id. | `proposal_ordering_violated` |
| ORP-INV-009 | single-turn core | Invoked tool name and args digest must match approved proposal. | `tool_args_digest_drift` |
| ORP-INV-010 | single-turn core | `commitment_recorded` must follow `tool_invoked`. | `commitment_missing_after_effect` |
| ORP-INV-011 | single-turn core | `turn_completed` must follow `commitment_recorded`. | `turn_not_completed_after_commitment` |
| ORP-INV-012 | single-turn core | Proposal model evidence must be present and anchored by matching model invocation, prompt, response, and proposal-extraction digests in the packaged full ledger payload when proposal claims depend on model-produced content. | `model_invocation_digest_drift` or `model_invocation_evidence_not_anchored` |
| ORP-INV-013 | denial path | Denied proposals must not be invoked. | `denied_proposal_invoked` |
| ORP-INV-014 | policy path | Policy-rejected proposals must not be invoked. | `policy_rejected_proposal_invoked` |
| ORP-INV-015 | deferred multi-turn | Turn-local sequence ordering must hold for each turn. | `multi_turn_sequence_ordering_violated` |
| ORP-INV-016 | single-turn core | Ledger ordering indexes must be strictly monotonic with no unexplained gaps. | `ledger_sequence_gap` |
| ORP-INV-017 | deferred multi-turn | `turn_completed(T)` must precede `turn_started(T+1)`. | `multi_turn_interleaving_violated` |
| ORP-INV-018 | deferred multi-turn | Turn `T` model evidence must link to prior governed results from turns `0..T-1`. | `cross_turn_result_linkage_missing` |
| ORP-INV-019 | deferred multi-turn | Tool at turn `T` must match the declared sequence entry. | `sequence_tool_order_violated` |
| ORP-INV-020 | deferred multi-turn | Completed sequences must have exactly the declared number of tool effects unless terminally stopped. | `sequence_length_violated` |
| ORP-INV-021 | deferred ODR | Deterministic posture requires ODR evidence and campaign-backed matching canonical hashes. | `odr_determinism_not_proven` |
| ORP-INV-022 | single-turn path family | Any absence claim requires a full canonical `ledger_export.v1` with `export_scope=all`; partial views cannot prove absence. | `full_ledger_export_required` |

## Missing Evidence Policy

The verifier must emit a failure or blocker for every missing evidence condition. It must not silently pass an invariant when required evidence is absent.

## Invariant Signature

The invariant signature must be stable across equivalent successful runs and exclude:
1. timestamps,
2. run-specific UUIDs,
3. session-local absolute paths,
4. model-generated text content,
5. generated bundle ids.

Signature material must include:
1. invariant schema version,
2. compare scope,
3. operator surface,
4. each applicable `ORP-INV-*` id and status,
5. assigned claim posture,
6. sorted missing-evidence codes.

## Acceptance Record

The active invariant checker is `scripts/proof/outward_run_invariant_checker.py`.

Accepted proof artifacts:
1. `benchmarks/results/proof/outward_run_witness_report.json`
2. `benchmarks/results/proof/outward_run_corruption_report.json`

The approved-path corruption suite passed for implemented package, ledger, artifact, invariant, and claim-tier corruptions. Denial, policy-rejection, and out-of-scope path-family fixtures remain explicit blockers.
