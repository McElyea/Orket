# Immutable planner and router inputs

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.46 candidate, 2026-09-20.
- Durable contract: `docs/specs/DISPATCH_DECISION_INPUTS.md`.

## Delta and migration
Planner inputs were mutable copied card models. Routers received application-owned
issue/team objects and could change later dispatch inputs through those references.
Application now captures explicit immutable contracts. Planner output remains
advisory ID selection; authoritative records and accepted-dependency checks remain
application-owned. Router returns must be plain strings before application policy.

Custom planners consume declared `PlanningCardInput` fields and immutable sequences.
Custom routers implement `route(RoutingInput)` instead of accepting issue/team models.
No alternate signature retry, hidden context lookup or mutable fallback is provided.
The default planner status/order rules and router guard-seat ordering are preserved.
The imported `PlanningInput` used by the existing protocol/export now refers to its
single authoritative core definition; no second definition is retained.

The legacy domain namespace remains unchanged under the accepted BT-4 compatibility
commitment. Its import warnings and alias state remain D debt until the explicit
0.7.0 cutover after caller inventory and contract acceptance. No classification or
dependency exception is changed to relabel that debt as compliance.

## Verification and rollback
Require retained pre-change mutation counterexamples, immutable nested-value and
deterministic recommendation controls, actual SQLite/orchestrator refusal and
dispatch parity, affected source/installed regressions, package parity and the
unchanged dependency gate. The canonical plan records observed proof and blockers.

Rollback this boundary and callers together on incompatible dispatch behavior;
retain failed observations and restore matching authority. No stored record,
acceptance receipt, dependency definition or durable schema is rewritten.

## Versioning decision
- Patch remediation checkpoint with an explicit breaking strategy API delta.
- Existing custom routers must migrate; undeclared planner model fields are retired.
- Other decision families, adapter enforcement, asynchronous reachability, Linux
  clock acceptance and whole-lane acceptance remain open.
