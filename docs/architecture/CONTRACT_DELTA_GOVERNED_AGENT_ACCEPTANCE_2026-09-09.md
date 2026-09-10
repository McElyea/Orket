# Governed Agent Acceptance Reconciliation

Date: 2026-09-09
Owner: Orket Core
Status: Implemented; final proof reconciliation in progress

## Summary

The Slice 7 audit found initial delivery of both fixture batches, unmaterialized
final-result references, inactive progress counters, and effect preparation
despite incorrect report contents. These gaps prevented truthful acceptance.
Affected authority: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.

## Delta

1. Host-only continuation inputs bind the run configuration, persist with wakes,
   and materialize the selected batch only after a continuation decision.
2. The external reference projects the latest prior report and excludes already
   counted batches before planner inference. JSON parsing is a declared stdlib
   dependency. Partial reports permit one source reference.
3. Fixture verifier v2 validates exact partial counts, source contents and refs.
   Invalid effect-bearing reports enter recovery before effect preparation.
4. Success points to the retained iteration-result record. Policy failures and
   exhausted progress budgets publish unsuccessful terminal truth.
5. `governed_agent_progress.v1` adds replayable verifier projection and counter
   fields; model narration cannot establish progress.
6. Shared SDK fixture helpers provide three fixed cases, including empty batch A.
7. Authenticated pause/stop targets an exact undecided invocation. Canonical
   operator actions and decision publication share an atomic boundary; late
   controls fail closed. Pause resumes under existing checkpoint authority.
8. Objective memory projects prior verified results, bounded to the same run
   and extension. One query per iteration is admitted; undeclared writes,
   foreign identity, and other memory scopes fail closed.
9. Pending approval resolution uses a conditional status update. After process
   loss at the write boundary, approval replay observes matching bytes and
   reconciles without repeating the write; missing bytes stay blocked.
10. SDK release workflow builds into its existing root `dist/` consumer path.
    The installed acceptance script records exact artifacts at one canonical
    local JSON path with diff-ledger history.
11. Built legacy/current compatibility proof identifies historical bundled SDK
    ownership and the required core-first, standalone-SDK-last wheel upgrade.
    The development prerelease compatibility claim is limited to matched
    candidate artifacts; old bundling hosts remain unsupported for overlays.

The existing oversized `async_repositories.py` grows by two lines to add the
conditional update to its authoritative pending-gate method. This is required
to prevent concurrent approved mutations without creating a second repository
authority; the file's broader size debt remains in architectural-truth.

## Migration Plan

Optional continuation input fields preserve existing requests without a plan.
Old hosts refuse the unknown dispatch field rather than silently dropping it.
For staged runs, author batch A in the initial request and batch B under key
`"2"` in the separate host plan. Keep that exact plan across retries. For the
effect acceptance flow set `effect_demo.proposal_iteration=2` and admit three
iterations: A, B plus prior report, then approved-effect resume.

Existing proof artifacts remain historical. Their unmaterialized
`agent-fixture-result:*` references are not rewritten or promoted to new proof.
New SDK/core/external artifacts require clean build and installed runtime proof.

## Rollback Plan

Do not resume new staged runs on an older host. Retain SQLite evidence and
cancel or reconcile under the originating version. Code rollback alone cannot
reinterpret new configuration digests or manufacture missing report evidence.

## Versioning Decision

Core patch candidate and SDK development prerelease update; exact release
versions and tags remain subject to the final repository release gates. No
release or whole-lane acceptance is implied by this delta.
