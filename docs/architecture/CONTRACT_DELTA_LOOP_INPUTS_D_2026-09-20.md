# Captured loop-policy inputs

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.48 candidate, 2026-09-20.
- Durable contract: `docs/specs/DISPATCH_DECISION_INPUTS.md`.

## Delta and migration
Loop and seat policies previously borrowed mutable issue records, and guard
validators could rewrite retained review payloads. A strategy `TypeError` could
also trigger a second call with a different signature.

Backlog methods now accept tuples of immutable `PlanningCardInput` values. Role
ordering takes a tuple captured before turn-transition awaits. The main loop binds
its selected node before settings observations and captures each backlog at the
declared repository observation boundary.

The six per-seat methods accept one `SeatPolicyInput`: captured card facts, seat,
turn status and resolved read/write paths. Custom implementations must use those
facts instead of borrowing an issue or arbitrary parameters. The application still
applies turn-contract overrides. Guard validation takes `GuardReviewInput`, with
immutable rationale, violations and remediation actions. No signature fallback
retries an entered strategy. Missing optional methods keep their existing defaults.

Name recommendations must be lists/tuples of plain strings; gate modes must be
plain strings. Boolean recommendation fields and exhaustion results are strict,
and unknown mapping fields fail. An empty name sequence remains permitted;
explicit `None` is no longer interpreted as an empty recommendation.

These are trusted in-process contracts. They neither contain hostile Python nor
freeze all runtime state. Existing transition, approval and accepted-completion
authority remains unchanged. Role refusal can follow a completed card transition;
earlier effects and evidence remain truthful and are not silently rolled back.

## Verification and rollback
Retain corrected pre-change borrowed-issue/review and duplicate-call controls,
independent published-version default outcomes, nested mutation/type refusals,
real SQLite/orchestrator completion checks and held-transition role capture. Run
affected source and installed regressions with exact origins and artifact binding.
The canonical plan records actual observations and outstanding acceptance gaps.

Rollback inputs, callers and custom strategies together. No durable schema or
historical completion/approval evidence is rewritten by this transition.

## Versioning decision
- Patch remediation checkpoint with an explicit breaking loop-policy API delta.
- Remaining sandbox/API/execution strategy inputs, adapter enforcement, async
  reachability, platform/coverage and CAP gates remain open; no lane retirement.
