# Core Runtime Requirements Slice Workboard

Last updated: 2026-03-06  
Status: Active (execution tracker)  
Owner: Orket Core

## Purpose

Track execution status, dependencies, and proof obligations for implementation slices defined in:
1. `runtime_requirements_implementation_plan.md`

## Slice Tracker

| Slice ID | Name | Status | Priority | Depends On | Primary Proof | Notes |
|---|---|---|---|---|---|---|
| CORE-IMP-00 | Contract Bootstrap | queued | P0 | none | Contract tests for registry/map validation | Establishes canonical contract sources. |
| CORE-IMP-01 | Deterministic Run Spine | queued | P0 | CORE-IMP-00 | Integration proof of ledger ordering + required invocation manifests | Hard invariant enforcement path. |
| CORE-IMP-02 | Golden Replay Integrity | queued | P0 | CORE-IMP-00, CORE-IMP-01 | Integration replay tests + compatibility rejection tests | Locks replay semantics and drift hierarchy. |
| CORE-IMP-03 | Ring Policy Enforcement | queued | P1 | CORE-IMP-00 | Static import boundary tests + dispatch rejection integration tests | Stops boundary drift. |
| CORE-IMP-04 | Compatibility Mapping Governance | queued | P1 | CORE-IMP-00, CORE-IMP-03 | Mapping contract tests + translation artifact integration tests | Enforces no-chaining + determinism propagation. |
| CORE-IMP-05 | Prompt Budget and Tokenizer Truth | queued | P1 | CORE-IMP-01 | Budget enforcement contract tests + backend-tokenizer integration tests | Prevents prompt drift and accounting mismatch. |
| CORE-IMP-06 | Reliability Scoreboard and Promotion Gates | queued | P1 | CORE-IMP-01, CORE-IMP-02, CORE-IMP-04 | Ledger-only reproducibility tests + promotion gate integration tests | Auditable reliability and promotion decisions. |
| CORE-IMP-07 | Compatibility Pilot Vertical Slice | queued | P2 | CORE-IMP-02, CORE-IMP-04, CORE-IMP-06 | Live+replay golden parity on pilot mappings | First end-to-end compatibility confidence pack. |

## Status Definitions

1. `queued`: not started.
2. `in_progress`: actively implementing.
3. `blocked`: cannot proceed due to explicit blocker.
4. `done`: implemented, verified, and closeout evidence recorded.

## Closeout Requirements Per Slice

1. Code changes merged for claimed behavior.
2. Required proof artifacts/tests executed and recorded.
3. Any unproven seams documented explicitly as residual risk.
4. Tracker row status moved to `done` only after proof is attached.

## Blocker Logging Format

Use this format when a slice becomes blocked:

```text
Slice: CORE-IMP-XX
Blocker: <short blocker title>
Type: environment | dependency | design | test-gap
Impact: <what cannot proceed>
Next action: <smallest unblock step>
```
