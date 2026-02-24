# OS Next Part - v1 Requirements

Last updated: 2026-02-24
Status: Paused draft
Owner: Orket Core

## Scope
Define the next OS v1 slice that productizes replay comparator behavior as a first-class runtime/API capability (not script-only).

## Objective
Ship a runtime comparator surface that is contract-safe, deterministic, and gate-enforced across kernel and API boundaries.

## In Scope
1. Add runtime/service comparator path that uses the same deterministic laws as `scripts/replay_comparator.py`.
2. Expose comparator inputs/outputs via existing kernel API boundaries.
3. Enforce comparator law checks in CI as mandatory gates.
4. Keep replay report ordering, report-id nullification, and IssueKey multiplicity behavior stable.

## Out of Scope
1. New distributed/remote replay architecture.
2. UI/UX replay visualization work.
3. Policy language redesign.

## Hard Requirements
1. Comparator behavior must remain deterministic for identical inputs.
2. Registry digest mismatch must fail closed with `E_REGISTRY_DIGEST_MISMATCH`.
3. Digest/version mismatch must emit `E_REPLAY_VERSION_MISMATCH`.
4. Issue comparison must use IssueKey multimap semantics with cardinality checks.
5. Safe boundary fields (`events`, `KernelIssue.message`, mismatch diagnostics) must not affect parity result.
6. Replay report ID must be derived by nullifying `report_id` and `mismatches[*].diagnostic` before hashing.
7. API responses must conform to `contracts/replay-report.schema.json`.

## Contract Inputs
1. `docs/projects/OS/contracts/stage-order-v1.json`
2. `docs/projects/OS/contracts/replay-bundle.schema.json`
3. `docs/projects/OS/contracts/replay-report.schema.json`
4. `docs/projects/OS/contracts/digest-surfaces.md`
5. `docs/projects/OS/contracts/canonicalization-rules.md`

## Deliverables
1. Runtime comparator module under `orket/kernel/v1/` (or service seam) replacing script-only reliance.
2. Comparator integration wiring through `orket/application/` and `orket/interfaces/`.
3. Regression tests for law set and ordering invariants.
4. Gate update documenting mandatory comparator suite.

## Acceptance Criteria
1. `python -m pytest -q tests/kernel/v1` passes with comparator runtime tests included.
2. `python -m pytest -q tests/interfaces/test_api_kernel_lifecycle.py` validates comparator response contract.
3. Comparator mismatch ordering is deterministic by `(turn_id, stage_index, ordinal, surface, path)`.
4. Report ID remains stable across equivalent runs and ignores diagnostic-only changes.
5. CI fails when comparator law behavior drifts.

## Initial Execution Order
1. Move/port comparator logic from `scripts/replay_comparator.py` to runtime seam.
2. Add kernel-level tests for registry lock, version mismatch, safe boundary, multiplicity, and report-id rules.
3. Wire API compare/replay handlers to runtime comparator path.
4. Promote gate checks in workflow and test policy text.
