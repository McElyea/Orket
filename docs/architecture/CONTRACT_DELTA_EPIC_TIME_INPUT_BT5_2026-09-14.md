# Epic bootstrap time input convergence

## Summary
- Change title: Bind epic bootstrap to its supplied runtime clock.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contracts: `EPIC_RUNTIME_TIME_INPUTS.md`, `CORE_RUNTIME_STABILITY_REQUIREMENTS.md`.

## Delta
- Current behavior: outcome/publication receive `RuntimeInputService` time, while
  epic bootstrap omits the existing `now` argument and reads another wall clock.
- Proposed behavior: capture bootstrap time through the selected input service
  and pass it explicitly to identity/workspace snapshot creation.
- Reason: supplied synthetic time cannot govern the composed run when bootstrap
  silently selects a different clock. Four controlled failures reproduce this
  independently of the retained Linux negative-duration observation.

## Migration Plan
1. Existing immutable identities retain their start time. No backfill or replay.
2. Existing default UTC behavior, summary failure and ledger-ordering contracts
   stay intact; deliberately reversed inputs retain explicit refusal/degradation.
3. Validate ordered and reversed composed paths, current source/installed package
   parity, retained histories and actual installed provider flows before acceptance.

## Rollback Plan
1. Trigger: input mismatch, altered original result or weakened refusal semantics.
2. Stop the affected proof and preserve original artifacts for repair.
3. A passing uncontrolled-clock rerun does not invalidate a retained failure.

## Versioning Decision
- No schema or compatibility alias change; one missing input is wired through
  an existing application service and artifact-capture argument.
- Effective version: unreleased worktree candidate. Package rebuild and current
  acceptance evidence are required; older wheel checks do not prove this change.
