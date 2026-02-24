# OS v1.2 Execution Pack

Last updated: 2026-02-24
Status: Active (authoritative for v1.2 execution)

This folder contains the authoritative v1.2 execution packet.

Lifecycle:
1. Use this pack to implement and validate PR-01 through PR-07.
2. Promote completed deliverables into `docs/projects/OS/contracts/*`, runtime code, and tests.
3. Archive this folder after v1.2 closeout.

## Files
1. `contract-delta.md`: contract/schema change scope for v1.2.
2. `sovereign-laws.md`: machine-testable law set.
3. `migration-matrix.md`: current -> target artifact mapping with break risk.
4. `implementation-plan.md`: execution sequence and PR dependency graph.
5. `pr-workboard.md`: per-PR file touch lists and acceptance checklists.
6. `open-decisions.md`: locked versioning/compatibility decisions.

## Review Order
1. `open-decisions.md`
2. `contract-delta.md`
3. `sovereign-laws.md`
4. `migration-matrix.md`
5. `implementation-plan.md`
6. `pr-workboard.md`

Current state:
1. D1-D9 are locked.
2. PR-01 through PR-07 are documented with execution-ready checklists.
