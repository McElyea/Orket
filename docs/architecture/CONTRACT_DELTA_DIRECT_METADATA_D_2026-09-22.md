# Artifact and source-attribution filesystem ownership

## Summary
- Change title: Capture artifact and receipt inputs and own their native work.
- Owner: Orket Core.
- Date: 2026-09-22.
- Affected contracts: `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` and
  `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`.

## Delta
- Current behavior: Artifact resolution and receipt existence checks block the
  event loop. Later caller/cwd mutation can change artifact inputs or receipt
  selection. Cancelled receipt reads can leave admitted native handles behind.
  Valid non-object JSON incorrectly bypasses required claim/source sufficiency.
- Proposed behavior: Capture inputs before yielding; use existing native/file
  owners through interruption. Observe receipt existence and contents in one
  native operation, closing the file before settlement. Non-object receipts carry
  the existing missing-claims and missing-sources classifications, so required
  mode blocks and optional mode remains unverified.
- Why now: Identical source and exact installed .97 controls reproduce 16 failures
  in 20 cases, with four healthy controls. The non-object correction enforces the
  existing non-empty claim/source requirement; it admits no new capability.

## Migration Plan
1. Compatibility window: Public signatures and persisted formats remain; no shim.
2. Migration steps: Retain interrupted calls through admitted native work. Treat
   non-object receipts as insufficient evidence and provide valid claims/sources.
   Recompute fresh summaries when needed; do not rewrite retained historical proof.
3. Validation gates: Actual files, path/cwd/input mutation, SQLite responsiveness,
   repeated cancellation, caller timeout, native failure, handle closure and
   receipt sufficiency; existing workload/summary behavior and installed matrices.

## Rollback Plan
1. Trigger: Changed authorized artifacts, hashes, policy or provenance projection.
2. Steps: Revert this scoped implementation while preserving observed failures.
3. State recovery: Artifact bundles can be partial after interruption. Preserve
   written evidence; no automatic rollback, new cloud effect or proof resealing.

## Versioning Decision
- Version bump type: Pre-1.0 patch with explicit interruption/input semantics.
- Effective version/date: 0.6.98 / 2026-09-22, subject to scoped acceptance.
- Downstream impact: Callers await native settlement; mutable caller/cwd state no
  longer changes admitted inputs. Non-object receipts no longer claim verification.
  No whole packet-2, Terraform cloud/model, hard filesystem deadline or hostile
  containment acceptance is implied.
