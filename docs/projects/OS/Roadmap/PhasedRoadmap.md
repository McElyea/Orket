# OS Phased Roadmap

Last updated: 2026-02-22
Status: Draft

## Phase 0: Program Contract Freeze
1. Confirm kernel API v1 boundary.
2. Confirm deterministic logging and replay baseline.
3. Confirm state integrity baseline (orphan-link, triplet rules).

## Phase 1: Kernelization
1. Create runtime kernel module boundary (`orket/kernel/v1`).
2. Move stage engine from CI script into kernel service.
3. Add kernel API contract tests.

## Phase 2: Stateful Integrity
1. Promote sovereign index from fixture to runtime-managed source.
2. Enforce orphan-link checks at runtime and CI gates.
3. Add batch/link integrity diagnostics.

## Phase 3: Capability Security
1. Add kernel capability resolution API.
2. Add tool authorization API with deterministic deny reasons.
3. Add policy compatibility tests.

## Phase 4: Replay and Equivalence
1. Add run-level replay API.
2. Add deterministic equivalence API and reports.
3. Gate deterministic claims on comparator pass.

## Phase 5: Rollout
1. Environment flags and progressive enforcement.
2. Runbook and triage paths.
3. Archive completed phase specs as needed.

## Immediate 6-PR Execution Sequence
1. PR1 Deletion lock-in:
implement tombstone parsing/update and make Law-6 tests green with tombstones.
2. PR2 LSI visibility fix:
resolve targets from sovereign index + staged created-set only; links cannot self-authorize.
3. PR3 Sequential promotion:
persist and enforce `last_promoted_turn_id`.
4. PR4 Error code normalization:
align runtime codes to canonical registry and enforce registry check test.
5. PR5 Sovereign test consolidation:
one canonical kernel-law test home and mandatory CI gate.
6. PR6 API boundary wiring:
thin kernel handlers for schema DTO round-trip request/response validation.
