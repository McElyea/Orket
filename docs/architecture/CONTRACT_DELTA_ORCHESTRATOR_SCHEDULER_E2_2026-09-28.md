# Orchestrator team scheduling ownership

## Summary
- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; scoped Windows source parity passed.
- Contract: `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.

## Delta
Team policy consumes explicit threshold/settings/organization observations in
original order. `TeamReplanScheduler` owns the single per-run count map and the
ordered replan/dependency operations. It receives narrow effect/policy ports;
current card and publication owners remain selected at their original phases,
including after child persistence. Counts advance before effects and do not roll
back on later failure. Child/publication/reset partial effects remain explicit.
Six private facade forwarders and duplicated facade count storage are retired.
Provider preparation/dispatch/finally, transition and completion authority remain.

Operations shrink 947 to 728 lines; coordinator 365 to 358. New modules are 86/189
lines, largest functions 32/51. Existing epic execution grows 202 to 213 only for
explicit composition ports and remains oversized debt. This is a bounded E2
reduction, not completion of orchestration decomposition or ambient-input work.

## Migration Plan
Use the actual scheduler owner for direct private-phase embeddings. No proxy,
compatibility wrapper or copied coordinator is introduced. Five native card/
publication controls retain owner-rebinding order, cancellation/failure partial
state and count limits. They are direct phase controls; broader public engine
proof uses supplied providers and does not establish live inference.

Baseline: **502 passed, 2 failed across 45 selectors; 5,584 inputs unchanged. The two additional direct Agent logging callers were repaired before product changes; all seven cases in that module then passed**. Closing: **697 passed across 63 selectors; 5,586 Git-visible inputs unchanged**. Existing
assertions and all five new phase bodies are preserved across declared owner
substitutions. Six logging caller repairs precede this window; two additional Agent bindings
were repaired and separately checked before product application;
the earlier 427/19 observation remains separate. Evidence is the before-v2 and
closing-v3 campaign under `.tmp/goal-20260928-epic-scheduler-composition-*`.
Proof: live local cards/publication/engine flows and structural parity,
primary/success. Installed, Linux and complete E2 remain unverified.

## Rollback Plan
Revert the focused owners, composition and private consumers together if ordering,
state identity or runtime parity fails. Preserve cards/publication records and
inspect them before retry; failure is not evidence that child persistence rolled back.

## Versioning Decision
Current 0.6.114 source candidate; no bump or capability admission. Private removed
helpers are deliberately migrated without compatibility shims. Existing exception
classification and oversized execution bodies remain disclosed debt.
