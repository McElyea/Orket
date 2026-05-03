# Outward Run Witness v1

Last updated: 2026-05-02
Status: Active durable contract for the approved single-turn outward proof kernel
Owner: Orket Core

Originating closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`
Slice authority: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/02-outward-run-witness-bundle/OUTWARD_RUN_WITNESS_BUNDLE_SLICE.md`
Deferred extensions: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

This contract is active for the `outward_run_write_file_approved_v1` single-turn approved path proven by the archived outward-run proof kernel closeout. Denial, policy-rejection, out-of-scope, multi-turn, ODR, and public-trust extensions remain outside this active boundary until their package fixtures and same-change authority updates exist.

## Purpose

Define the portable witness package, evidence bundle, offline verifier surface, campaign report surface, and missing-evidence vocabulary for the outward-facing run pipeline.

This spec is the outward-pipeline analogue of `docs/specs/TRUSTED_RUN_WITNESS_V1.md`. It depends on and does not replace that spec, the trusted-run invariant model, or the finite trust kernel model.

## Non-Goals

This spec does not:
1. claim the outward run pipeline is mathematically proven in general,
2. widen the public trust boundary defined in `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`,
3. replace trusted-run witness, invariant, or substrate contracts,
4. describe model output correctness or provider semantics,
5. define the outward run API or CLI surface.

## Witness Package Schema

Schema version string: `outward_run_witness_package.v1`

The independently checkable proof object is a package:

```text
outward_run_witness_package.v1/
  manifest.json
  outward_witness_bundle.json
  ledger_export.json
  artifacts/
    committed_output
```

The verifier consumes package files only. Bundle-only verification may validate schema and internal commitments, but it cannot prove full ledger integrity, event absence, or committed artifact bytes. A bundle-only mode must not return `accepted` for proof claims.

`manifest.json` must include:
1. `schema_version`
2. `package_id`
3. `compare_scope`
4. `bundle_path`
5. `ledger_export_path`
6. `artifact_paths`
7. `package_digest`

## Bundle Schema

Schema version string: `outward_run.witness_bundle.v1`

A bundle is a single JSON object inside the witness package. Digest fields are lowercase SHA-256 hex strings. Timestamp fields are metadata only; ordering authority comes from the full packaged `ledger_export.v1`.

### Required Top-Level Fields

| Field | Type | Classification | Notes |
|---|---|---|---|
| `schema_version` | string | authority | Must equal `outward_run.witness_bundle.v1` |
| `bundle_id` | string | derived | Producer-assigned id |
| `run_id` | string | authority | Must align across all evidence |
| `produced_at_iso` | string | metadata | Not ordering authority |
| `compare_scope` | string | authority | Must be an admitted scope |
| `operator_surface` | string | authority | Must be `outward_run_witness_report.v1` |
| `claim_tier_request` | string | claim | Lane-local outward claim posture until tier spec is active |
| `run_authority` | object | authority | Run record projection with digest |
| `approval_authority` | array | authority | One entry per proposal |
| `ledger_evidence` | object | authority | Event log and ledger hash evidence |
| `effect_evidence` | array | authority | One entry per tool invocation |
| `model_invocation_evidence` | array | derived | Digests must be authority-anchored |
| `policy_identity` | object | authority | Governing policy at submission time |
| `artifact_refs` | array | authority/derived | Per-entry classification |
| `package_refs` | object | authority | Relative package paths for ledger export and artifacts |

### `run_authority`

Required fields:
1. `run_id`
2. `namespace`
3. `status`
4. `run_status`
5. `submitted_at_iso`
6. `task_description`
7. `task_instruction`
8. `acceptance_contract_tool`
9. `acceptance_contract_sequence`
10. `policy_overrides_digest`
11. `run_record_digest`

### `approval_authority`

Each entry must include:
1. `approval_id`
2. `run_id`
3. `turn_index`
4. `tool_name`
5. `tool_args_digest`
6. `status`
7. `decided_at_iso`
8. `approval_record_digest`

Allowed `status` values are `approved`, `denied`, `expired`, and `policy_rejected`.

### `ledger_evidence`

Required fields:
1. `ledger_export_schema`
2. `run_id`
3. `event_count`
4. `export_scope`
5. `ledger_hash`
6. `events`
7. `ledger_export_digest`
8. `ledger_export_package_path`

Each event entry may carry `event_type`, `position`, `sequence_index`, `event_hash`, `previous_chain_hash`, `chain_hash`, and `event_payload_digest` as summary evidence.

Independent full-ledger verification requires the package to include the full `ledger_export.v1` JSON bytes. Hashing, chain, partial-view, and full-export semantics are delegated to `docs/specs/LEDGER_EXPORT_V1.md`.

Digest-only ledger summaries are commitments, not authority for absence or completeness.

### Model Evidence Anchor Rule

For ORP-INV-012, model evidence is anchored only if the packaged full ledger export contains the `proposal_made` payload fields naming the model invocation, prompt, response, and proposal-extraction digests, and those digests match the bundle's `model_invocation_evidence` entry.

This proves only that the proposal was recorded with anchored model-evidence digests. It does not prove provider output semantics, replay the model call, or validate that the model reasoned correctly.

### Admitted Initial Event Types

| Event type | Significance |
|---|---|
| `run_submitted` | Admission before effects |
| `run_started` | Execution begun |
| `turn_started` | Model-call cycle begun |
| `proposal_made` | Model produced governed proposal |
| `proposal_pending_approval` | Proposal entered approval queue |
| `proposal_approved` | Human approved proposal |
| `proposal_denied` | Human denied proposal |
| `proposal_expired` | Proposal timed out |
| `proposal_policy_rejected` | Policy rejected proposal |
| `tool_invoked` | Connector effect applied |
| `commitment_recorded` | Effect committed durably |
| `turn_completed` | Model-call cycle complete |
| `run_completed` | Terminal run truth |

### Verifier Report Schema

Schema version: `outward_run_witness_report.v1`

Required fields:
1. `schema_version`
2. `bundle_id`
3. `run_id`
4. `compare_scope`
5. `result`
6. `claim_tier_request`
7. `claim_tier_assigned`
8. `invariant_model`
9. `missing_evidence`
10. `invariant_signature`

Allowed `result` values are `accepted`, `rejected`, and `downgraded`.

### Campaign Report Schema

Schema version: `outward_run_campaign_report.v1`

Required fields:
1. `schema_version`
2. `compare_scope`
3. `run_count`
4. `accepted_count`
5. `invariant_signature_stable`
6. `invariant_signature`
7. `claim_tier_ceiling`
8. `missing_evidence_union`

## Digest Authority Rule

Any digest used as authority must be either:
1. recomputed from canonical bytes included in the witness package, or
2. anchored by a verified full `ledger_export.v1` payload field from the package.

A digest without source bytes or a verified ledger anchor is support-only or blocker-producing for authority claims.

## Absence Proof Rule

Any claim requiring absence of a later event must use a full canonical `ledger_export.v1` with `export_scope=all`. Partial views cannot prove absence or completeness.

## Offline Verifier Contract

The offline verifier must:
1. accept `--package` as the only proof input that can produce `accepted`,
2. read only files inside the witness package supplied on the command line,
3. not open any database handle,
4. not make network requests,
5. not call model providers,
6. not read process environment for policy, credentials, or runtime configuration,
7. produce identical output for identical input bytes.

Bundle-only mode, if implemented for debugging or introspection, is schema-only and cannot accept proof claims.

The offline verifier may import pure canonicalization helpers when those helpers do not consult mutable runtime state.

## Missing-Evidence Vocabulary

The active initial blocker vocabulary includes `package_manifest_missing`, `package_manifest_digest_mismatch`, `bundle_missing`, `package_ref_outside_package`, `ledger_export_missing`, `ledger_export_digest_mismatch`, `ledger_payload_bytes_missing`, `committed_artifact_missing`, `artifact_digest_mismatch`, `full_ledger_export_required`, `terminal_status_drift`, and `source_bytes_missing_for_digest` to prevent package-level false authority.

## Acceptance Record

Accepted commands and artifacts for the active boundary:
1. `python scripts/proof/run_outward_write_file_approved_proof.py`
2. `python scripts/proof/verify_outward_run_witness_package.py --package benchmarks/results/proof/outward_run_witness_package.v1 --scope outward_run_write_file_approved_v1 --output benchmarks/results/proof/outward_run_witness_report.json`
3. `python scripts/proof/validate_outward_write_file_committed.py --package benchmarks/results/proof/outward_run_witness_package.v1 --output benchmarks/results/proof/outward_write_file_validation.json`
4. `python scripts/proof/run_outward_run_corruption_suite.py --base benchmarks/results/proof/outward_run_witness_package.v1 --output benchmarks/results/proof/outward_run_corruption_report.json`

The verifier accepted the package from serialized package bytes only. Public trust wording remains unchanged.
