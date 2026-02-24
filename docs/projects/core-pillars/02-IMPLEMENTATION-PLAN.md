# Core Pillars Implementation Plan

Date: 2026-02-24  
Execution mode: vertical-slice, deterministic gates first

Canonical detailed execution ordering and slice DoR/DoD:
`docs/projects/core-pillars/08-DETAILED-SLICE-EXECUTION-PLAN.md`

## Phase 1: Build Layer Foundation
1. Implement command transaction shell requirements from `04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md`.
2. Implement `orket api add` as the primary CP-1 driver on existing repositories.
3. Implement deterministic test-template packs for generated routes (no general test generator in v1).
4. Implement minimal `orket init` blueprint hydration (template copy + variable fill).
5. Enforce API idempotency and extension-point contracts from `07-API-GENERATION-CONTRACT.md`.

## Phase 2: Trust Layer Foundation
1. Standardize replay record schema and storage interfaces.
2. Constrain replay to artifact recording and comparison (not a global policy engine).
3. Add replay comparison gate for generated code + refactors.
4. Implement verified-refactor flow with pre/post parity checks.
5. Add CI gates for deterministic drift detection.
6. Add acceptance tests for safety/rollback/barrier (`A1-A4`).

## Phase 3: State Layer Foundation
1. Harden vector memory contract and adapter seams.
2. Add persistent bot profile schema with role/governance limits.
3. Integrate memory-backed retrieval with replay traceability.
4. Add retention-aware artifact lifecycle for state/replay outputs.
5. Implement Bucket D failure-lesson memory from `05-BUCKET-D-FAILURE-LESSONS-REQUIREMENTS.md`.
6. Add D1-D4 memory acceptance tests and advisory-preflight behavior.

## Phase 4: Local Sovereignty Hardening
1. Define offline capability matrix and required fallback behavior.
2. Ensure baseline scaffolding, generation, replay, and tests run offline.
3. Add offline mode gate tests and runbook.

## Cross-Cutting Controls
1. Keep dependency policy contract authoritative.
2. Enforce no unknown layer classifications.
3. Require contract-delta template for boundary breaks.
4. Ratchet legacy-edge budget downward only with green full-suite validation.
5. Keep ideas extraction provenance at `06-IDEAS-TRIAGE-SPEC-VS-SPECULATION.md`.
6. Keep replay bounded in CP-2 to recording/comparison surfaces only; no cross-feature orchestration coupling.

## Validation Commands
1. `python scripts/check_dependency_direction.py --legacy-edge-enforcement fail`
2. `python scripts/export_dependency_graph.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m pytest -q`

## Risks
1. Scope spread across eight pillars causes delivery dilution.
- Mitigation: vertical slices tied to acceptance gates, not pillar count.
2. Generated code quality varies across targets.
- Mitigation: deterministic replay and contract tests as merge gates.
3. Offline requirement may conflict with convenience integrations.
- Mitigation: capability matrix with explicit optional online enhancements.
