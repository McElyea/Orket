# Slice 03 - Invariant Checker

Last updated: 2026-05-01
Status: Archived slice plan - approved single-turn invariants promoted
Owner: Orket Core

Parent closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_IMPLEMENTATION_PLAN.md`

## Purpose

Mechanize outward-run invariants so proof claims rest on checker output instead of prose.

## Invariant ID Prefix

All outward-run invariants use the `ORP-INV-*` prefix. This keeps outward pipeline invariants scope-local and avoids relabeling existing `TRI-INV-*`, `TRC-INV-*`, or `TTPD-INV-*` invariants.

## Invariant Table - v1 Draft

The accepted approved-path subset was extracted to `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`. Deferred path-family and extension coverage remains future-hold.

| ID | Activation | Invariant | Failure Code |
|---|---|---|---|
| ORP-INV-001 | single-turn core | `run_submitted` must appear before any `tool_invoked` event. | `effect_before_admission` |
| ORP-INV-002 | single-turn core | `proposal_approved` for a governed tool must appear before the corresponding `tool_invoked` event. | `effect_before_approval` |
| ORP-INV-003 | single-turn core | Terminal success requires exactly one terminal run event, success-class status alignment across run authority and ledger evidence, and no unresolved invoked effect without commitment. | `final_truth_missing`, `terminal_status_drift`, or `commitment_missing_after_effect` |
| ORP-INV-004 | single-turn core | A claim asserting an effect occurred requires a `tool_invoked` ledger event for the named tool and run. | `effect_evidence_missing` |
| ORP-INV-005 | single-turn core | Projection-only fields and digest-only commitments must not substitute for authority bytes or verified ledger anchors. | `projection_substituted_for_authority` or `source_bytes_missing_for_digest` |
| ORP-INV-006 | single-turn core | Ledger hash verification must recompute from the full packaged `ledger_export.v1` payload bytes for full-ledger claims; partial views must not claim completeness. | `ledger_export_missing`, `ledger_export_digest_mismatch`, `ledger_payload_bytes_missing`, `ledger_chain_broken`, or `ledger_chain_hash_mismatch` |
| ORP-INV-007 | single-turn core | The requested outward claim posture must not exceed the evidence-supported ceiling. | `claim_tier_not_supported` |
| ORP-INV-008 | single-turn core | `proposal_made` must precede `proposal_pending_approval` for the same approval id. | `proposal_ordering_violated` |
| ORP-INV-009 | single-turn core | The invoked tool name and args digest must match the approved proposal. | `tool_args_digest_drift` |
| ORP-INV-010 | single-turn core | `commitment_recorded` must follow `tool_invoked` for the same approval id or turn. | `commitment_missing_after_effect` |
| ORP-INV-011 | single-turn core | `turn_completed` must follow `commitment_recorded` for the same turn. | `turn_not_completed_after_commitment` |
| ORP-INV-012 | single-turn core | `proposal_made` model evidence must be present and anchored by matching model invocation, prompt, response, and proposal-extraction digests in the packaged full ledger payload when the proposal claim depends on model-produced content. | `model_invocation_digest_drift` or `model_invocation_evidence_not_anchored` |
| ORP-INV-013 | denial path | A `proposal_denied` event must not be followed by `tool_invoked` for the same approval id. | `denied_proposal_invoked` |
| ORP-INV-014 | policy path | A `proposal_policy_rejected` event must not be followed by `tool_invoked` for the same approval id. | `policy_rejected_proposal_invoked` |
| ORP-INV-015 | deferred multi-turn | Each turn in a governed sequence must preserve turn-local event ordering. | `multi_turn_sequence_ordering_violated` |
| ORP-INV-016 | single-turn core | Ledger event positions or sequence indexes used for ordering must be strictly monotonic with no unexplained gaps. | `ledger_sequence_gap` |
| ORP-INV-017 | deferred multi-turn | `turn_completed(T)` must precede `turn_started(T+1)`. | `multi_turn_interleaving_violated` |
| ORP-INV-018 | deferred multi-turn | Turn `T` model evidence must reference prior governed tool results from turns `0..T-1`. | `cross_turn_result_linkage_missing` |
| ORP-INV-019 | deferred multi-turn | Tool at turn `T` must match the `T`th declared tool in the governed sequence contract. | `sequence_tool_order_violated` |
| ORP-INV-020 | deferred multi-turn | A completed sequence must have exactly the declared number of invoked tool effects unless terminated early by denied, expired, or policy-rejected truth. | `sequence_length_violated` |
| ORP-INV-021 | deferred ODR | ODR determinism evidence must be present and campaign-backed before any outward deterministic posture can be assigned. | `odr_determinism_not_proven` |
| ORP-INV-022 | single-turn path family | Any claim requiring absence of a later event must use a full canonical `ledger_export.v1` with `export_scope=all`; partial views cannot prove absence. | `full_ledger_export_required` |

## Checker Input Contract

```text
Input: outward_run_witness_package.v1 package bytes/files
Input: admitted compare scope string
Input: requested outward claim posture
```

The checker reads only files inside the witness package. It must not import the Orket runtime, open the outward stores, call the API, read clocks, read process environment for policy, make network requests, invoke model providers, or read mutable workspace paths outside the package.

## Checker Output Contract

The checker writes `outward_run_witness_report.v1` JSON:

```json
{
  "schema_version": "outward_run_witness_report.v1",
  "bundle_id": "<string>",
  "run_id": "<string>",
  "compare_scope": "<string>",
  "result": "accepted",
  "claim_tier_request": "<string>",
  "claim_tier_assigned": "<string>",
  "invariant_model": {
    "schema_version": "outward_run_invariants.v1",
    "invariants": [
      {
        "id": "ORP-INV-001",
        "status": "passed",
        "failure_code": null,
        "detail": null
      }
    ]
  },
  "missing_evidence": [],
  "invariant_signature": "<sha256 hex>"
}
```

Allowed `result` values:
1. `accepted`: all applicable invariants passed and assigned posture equals request
2. `downgraded`: all applicable invariants passed but assigned posture is lower than request
3. `rejected`: one or more invariants failed or emitted a blocker

## Invariant Signature Rules

The invariant signature must be stable across equivalent successful evidence and exclude:
1. timestamps
2. run-specific UUIDs
3. session-local absolute paths
4. model-generated text content
5. generated bundle ids

Signature material must include:
1. invariant schema version
2. compare scope
3. operator surface
4. each applicable `ORP-INV-*` id and status
5. claim posture assigned
6. sorted missing-evidence codes

## Positive and Negative Test Requirements

Positive tests:
1. a valid `outward_run_write_file_approved_v1` witness package from a real governed-run fixture must be accepted
2. equivalent successful packages must produce the same invariant signature after normalization

Negative tests:
1. each entry in the corruption matrix must produce the expected failure code
2. missing `ledger_evidence` must fail closed
3. removing `proposal_approved` while leaving `tool_invoked` must produce `effect_before_approval`
4. presenting only digest commitments without source bytes or ledger anchors must produce `source_bytes_missing_for_digest`
5. absence claims over partial views must produce `full_ledger_export_required`
6. package-level manifest, ledger export, and artifact-byte corruptions must fail before any proof claim can be accepted

## Forbidden Shortcuts

1. do not count import-only, schema-only, or dry-run-only proof as runtime truth
2. do not accept a digest-only ledger summary as proof of approval, absence, or final truth
3. do not let projection fields substitute for authority refs or digests
4. do not emit `accepted` when any required invariant has `status=blocker`
5. do not allow a bundle-only verifier path to emit `accepted` for proof claims
