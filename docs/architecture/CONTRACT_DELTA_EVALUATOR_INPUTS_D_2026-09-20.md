# Captured evaluator inputs

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.47 candidate, 2026-09-20.
- Durable contract: `docs/specs/DISPATCH_DECISION_INPUTS.md`.

## Delta and migration
Failure evaluators previously received writable issue/result objects after an
awaited report publication. Success evaluators received an execution turn already
appended to the transcript and could rewrite it through that reference.

Both application handlers now capture their evaluator and immutable input facts
before their first await. Failure publication and decisions share the captured
error/violations/counts. Success evaluation combines its captured initial context
with the repository's subsequently observed status. Memory decision summaries use
the captured content. This does not assert an atomic whole-runtime snapshot.

Custom nodes migrate to `evaluate_failure(inputs)` and `evaluate_success(inputs)`.
Their mappings must match declared primitive recommendation fields: strict boolean
success flags, integer retry counts and string actions. Success post-action inputs
are copied read-only mappings; action/status fields are validated before use.
The existing exception/message policies and default retry, approval, guard and
status behavior remain. No implicit old-signature retry or mutable payload exists.

The application still owns effects and accepted-completion checks. This change
does not introduce a new retry-budget policy, freeze every application object or
provide hostile-code containment. Failure-report publication can precede a later
recommendation/mutation refusal and remains truthful retained evidence.

## Verification and rollback
Require retained pre-change mutation/await counterexamples, deterministic default
parity, rejected nested mutation and malformed recommendations, actual failure
files/SQLite inspection, held-await node/input rotation controls and affected
source/installed regressions. Record exact observations in the canonical plan.

Rollback contracts, handlers and callers together on incompatible behavior.
Preserve failure evidence; no durable schema, historical response timestamp,
accepted completion receipt or record is rewritten by this transition.

## Versioning decision
- Patch remediation checkpoint with an explicit breaking evaluator API delta.
- Custom nodes migrate their input signatures and recommendation values.
- Other decision families, complete adapter enforcement, asynchronous reachability,
  platform/coverage gates and explicit lane acceptance remain open.
