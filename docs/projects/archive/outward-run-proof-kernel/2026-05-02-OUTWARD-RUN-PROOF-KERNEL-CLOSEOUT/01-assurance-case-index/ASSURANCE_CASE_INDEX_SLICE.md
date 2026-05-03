# Slice 01 - Assurance Case Index

Last updated: 2026-05-02
Status: Archived slice plan - approved-path rows validated; path-family blockers future-hold
Owner: Orket Core

Parent closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_IMPLEMENTATION_PLAN.md`
Future extensions: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

## Purpose

Create the canonical map from outward-run proof claims to invariant ids, evidence artifacts, verifier commands, and allowed claim posture.

## Scope

This slice owns the lane-local assurance case structure. Durable schema or contract decisions extracted from this slice must move to `docs/specs/` before implementation code treats them as authority.

## Artifact Classification Rules

Every artifact that appears in the assurance case index must be classified as exactly one of:

| Class | Meaning |
|---|---|
| `authority` | Serialized record from the runtime store, ledger export, or witness bundle. Verifier may accept this in an authority slot. |
| `claim` | Verifier output produced from authority artifacts. Not self-authorizing. |
| `derived` | Computed summary, graph, or projection. Must carry source authority refs or digests. |
| `support-only` | Documentation, guide, SVG diagram, prose runbook. Cannot substitute for authority. |
| `forbidden-substitute` | A derived or support-only artifact presented where authority evidence is required. |

`forbidden-substitute` is a verifier rejection rule, not a desirable artifact type.

## Assurance Case Index - v1 Draft

The compare scope for all rows is `outward_run_write_file_approved_v1` unless the row explicitly names a path variant.

| Claim ID | Claim | Compare Scope | Operator Surface | Allowed Posture | Invariant IDs | Authority Evidence | Derived / Support Evidence | Verifier Command | Current Blocker |
|---|---|---|---|---|---|---|---|---|---|
| ORP-CLAIM-001 | The run was admitted before any effect occurred. | `outward_run_write_file_approved_v1` | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-001, ORP-INV-008 | `benchmarks/results/proof/outward_run_witness_package.v1/ledger_export.json`; outward run record digest in package bundle | run summary projection | `python scripts/proof/verify_outward_run_witness_package.py --package <package> --scope outward_run_write_file_approved_v1` | none for approved path; verifier output: `benchmarks/results/proof/outward_run_witness_report.json` |
| ORP-CLAIM-002 | No approval-required tool was invoked before an approved decision was recorded. | `outward_run_write_file_approved_v1` | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-002, ORP-INV-009 | packaged `proposal_approved` and `tool_invoked` ledger payloads; approval record digest in package bundle | run summary projection | same | none for approved path |
| ORP-CLAIM-003 | The invoked tool matches the model-produced proposal admitted for approval. | `outward_run_write_file_approved_v1` | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-009, ORP-INV-012 | packaged `proposal_made` full ledger payload carrying model invocation, prompt, response, and proposal-extraction digests; packaged approval/effect evidence | `proposal_extraction_turn_<n>.json` as support-only derived evidence | same | none for approved path |
| ORP-CLAIM-004 | The effect was committed and recorded after approval. | `outward_run_write_file_approved_v1` | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-004, ORP-INV-010, ORP-INV-011 | packaged `tool_invoked`, `commitment_recorded`, and `turn_completed` ledger events; `artifacts/committed_output` bytes | run events projection | same | none for approved path; artifact validation: `benchmarks/results/proof/outward_write_file_validation.json` |
| ORP-CLAIM-005 | The run reached a terminal success state with final-truth evidence. | `outward_run_write_file_approved_v1` | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-003 | packaged `run_completed` ledger event with success-class status; outward run record digest | run summary | same | none for approved path |
| ORP-CLAIM-006 | The full ledger hash chain is intact. | `outward_run_write_file_approved_v1` | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-006, ORP-INV-016 | full packaged `ledger_export.v1` JSON bytes | ledger export summary | same | none for approved path |
| ORP-CLAIM-007 | A denied proposal produced no tool invocation or commitment. | `outward_run_write_file_approved_v1` denial path | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-013, ORP-INV-022 | `proposal_denied` ledger event; full `export_scope=all` ledger export proving absence | run events projection | same | denial base fixture required |
| ORP-CLAIM-008 | A policy-rejected proposal produced no tool invocation or commitment. | `outward_run_write_file_approved_v1` policy path | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-014, ORP-INV-022 | `proposal_policy_rejected` ledger event; full `export_scope=all` ledger export proving absence | run events projection | same | policy-rejection base fixture required |
| ORP-CLAIM-009 | An out-of-scope model proposal was rejected before human approval. | `outward_run_write_file_approved_v1` out-of-scope path | `outward_run_witness_report.v1` | `outward_lab_only` | ORP-INV-014, ORP-INV-022 | `proposal_policy_rejected` ledger event with out-of-scope reason; full ledger export proving absence of approval resolution | approval queue projection | same | out-of-scope fixture required |
| ORP-CLAIM-010 | Equivalent successful evidence produces a stable invariant signature. | `outward_run_write_file_approved_v1` campaign | `outward_run_campaign_report.v1` | `outward_verifier_stable` | ORP-INV-001 through ORP-INV-016, ORP-INV-022 where absence is claimed | two or more accepted verifier reports with matching invariant signatures | campaign report | `python scripts/proof/run_outward_run_witness_campaign.py --report <report-a> --report <report-b> --output <campaign-report>` | none for approved-path verifier stability; path-family absence fixtures still blocked |

## Required Outputs Status

| Output | Status |
|---|---|
| claim id and one-sentence claim | Drafted above; approved-path evidence paths added |
| compare scope per claim | Drafted above |
| operator surface | `outward_run_witness_report.v1` for single-run claims; `outward_run_campaign_report.v1` for campaign claim |
| allowed posture | Drafted above; see Slice 06 |
| invariant ids | Accepted for approved path through `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`; path-family rows remain blocked |
| authority-bearing evidence refs | Accepted for approved path through packaged evidence; denial, policy-rejection, and out-of-scope authority evidence remains blocked |
| support-only evidence refs | Drafted above |
| verifier command | Package verifier, artifact validator, corruption suite, and campaign runner implemented for approved path |
| current blockers | Denial, policy-rejection, and out-of-scope fixtures remain explicit blockers |

## Forbidden Shortcuts

1. do not create broad mathematical-proof wording
2. do not duplicate the public trust reason contract
3. do not treat docs, guides, graphs, summaries, or ledgers as equivalent authority without source evidence classification
4. do not mark a blocker as resolved until the verifier command has been run and its output is captured

## Extraction Record

The machine-readable row schema was extracted to `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md`. Path-family blockers are tracked in `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`.
