# Docs Gate Milestones

Date: 2026-02-24  
Status: archived

## Status Snapshot
1. DG-1 Requirements and contracts: completed.
2. DG-2 `docs_lint.py` implementation (DL1-DL3): completed.
3. DG-3 Acceptance harness and CI integration: completed.
4. DG-4 Optional strict/crossref expansion: completed.

## DG-1: Requirements Freeze
1. Lock command, exit, error-code, and output contracts.
2. Lock DL1-DL3 acceptance definitions.

Exit criteria:
1. Requirements and implementation plan documents approved.
2. Project appears in `docs/ROADMAP.md` project index.

## DG-2: Script Delivery
1. Deliver `scripts/docs_lint.py` with deterministic checks.
2. Enforce `DL1-DL3` and contract-stable reporting.

Exit criteria:
1. Local script pass/fail behavior matches requirements.
2. Deterministic ordering verified by tests.

## DG-3: Test and CI Gate Delivery
1. Deliver `tests/acceptance/docs_gate/` runner and fixtures.
2. Wire docs gate into quality workflow.
3. Add workflow gate assertions for docs-lint command presence.

Exit criteria:
1. `DL0-DL3` acceptance suite passes.
2. Quality workflow includes docs-gate invocation.

## DG-4: Controlled Expansion (Optional)
1. Add strict-mode and scoped cross-reference checks after DG-3.
2. Keep backward-compatible output schema and error codes.

Exit criteria:
1. Expanded checks remain deterministic.
2. No regressions to DG-2/DG-3 contracts.
