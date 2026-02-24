# v1.2 Implementation Plan (Execution-Ready Proposal)

Last updated: 2026-02-24
Status: Execution-ready proposal (non-authoritative until promotion)
Owner: Orket Core

## Objective
Ship the locked D1-D9 decisions as a mergeable PR sequence that hardens contracts, replay parity, and capability correspondence without silent `kernel_api/v1` semantic swaps.

## Scope
In scope:
1. Contract artifacts and schemas for stage order, decision records, replay bundle/report, and digest surfaces.
2. Comparator behavior tightening (IssueKey ordering, multiplicity, deterministic report identity).
3. Kernel emission and digest computation updates required by D2, D3, D4, D6, D7, and D8.

Out of scope:
1. Non-parity UX/reporting enhancements.
2. New capability policy language.
3. Distributed runtime changes.

## Locked Inputs
1. `open-decisions.md` is authoritative for D1-D9.
2. `sovereign-laws.md` is the law source for parity behavior.
3. Contract path convention is `docs/projects/OS/contracts/*`.

## PR Dependency Graph
1. `PR-01` is the foundation and must land first.
2. `PR-02` depends on `PR-01`.
3. `PR-03` depends on `PR-01`.
4. `PR-04` depends on `PR-01` and can run in parallel with `PR-02` and `PR-03`.
5. `PR-05` depends on `PR-01`, `PR-03`, and `PR-04`.
6. `PR-06` depends on `PR-02` and `PR-05`.
7. `PR-07` depends on `PR-04` and `PR-06`.

## Sequence Summary

| PR | Title | Primary Deliverable | Must Preserve |
|---|---|---|---|
| PR-01 | Stage spine + registry wrapper | Stage order contract and deterministic registry digest support | No kernel behavior changes |
| PR-02 | CapabilityDecisionRecord coexistence | New parity decision schema and TurnResult coexist field | Existing capability shape remains valid |
| PR-03 | Replay bundle/report contracts | Authoritative replay input/output schema tightening | Additive compatibility for current report consumers |
| PR-04 | Canonicalization and digest law docs | Written byte-law and digest-surface definitions | Nullification-over-omission consistency |
| PR-05 | Comparator implementation | Deterministic comparator gate with IssueKey multimap and stable `report_id` | Safe boundary diagnostics excluded from parity |
| PR-06 | Kernel decision emission wiring | One decision record per tool attempt + correspondence law | Deterministic capability stage/location/code behavior |
| PR-07 | TurnResult digest surface | Contract-only digest computation in runtime | Diagnostics do not affect digest |

## Working Agreement
1. No PR may silently change meaning of an existing v1 field.
2. Excluded hash fields are nullified, never removed.
3. Comparator ordering uses contract stage order, never host/runtime array arrival order.
4. Each PR must be independently mergeable and include its own test updates.

## Definition of Done
1. All acceptance checks in `pr-workboard.md` are satisfied for each landed PR.
2. CI architecture gates remain green, including:
   - `python scripts/audit_registry.py`
   - `python -m pytest -q tests/kernel/v1`
   - `python -m pytest -q tests/interfaces/test_api_kernel_lifecycle.py`
   - `python scripts/run_kernel_fire_drill.py`
3. Promotion to authoritative docs occurs only after PR-07 merge and final review.

## Execution Artifact
Detailed work packages, exact file touch lists, and acceptance checklists live in `pr-workboard.md`.
