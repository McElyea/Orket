# Execution Graph Retained Acceptance

## Summary
- Change title: Align operator dependency labels with retained card acceptance.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and
  `docs/API_FRONTEND_CONTRACT.md`.

## Delta
- Opening behavior: the execution graph treats done, guard-approved and archived
  rows as satisfied without inspecting acceptance, and rejects valid prerequisites
  absent from the displayed session.
- Required behavior: application-owned inspection reads session cards and their
  prerequisites under one card writer guard. Dependency resolution reuses the
  dispatch context's current receipt, evidence and build-scope checks. Each node
  separately reports lifecycle, retained completion acceptance and dependency
  rejection reasons. `blocked` means a prerequisite is rejected, regardless of the
  node's lifecycle. It is not a prediction of planner selection.
- `unresolved_dependencies` retains its graph meaning: references outside the
  displayed node set. New `accepted_dependency_receipts` and
  `dependency_rejections` explain whether those references resolve for execution.
  A same-build accepted prerequisite outside this view can satisfy a dependency.
- Graph ordering and handoff edges remain observational. The graph is not a
  completion receipt or a permanent assertion about workspace contents.
- Snapshot persistence becomes an application-owned, guarded workspace write.
  A persistence failure is logged without replacing a valid inspection response.

## Migration Plan
1. Keep the endpoint and existing graph fields; add acceptance diagnostics.
2. Add typed session inventory to the repository port. No database migration or
   recapture of historical evidence. Unsupported parent relationships are not
   inferred from canonical card records, which have no parent field.
3. Exercise authenticated API positives and negatives with real stores, repeated
   reads after evidence loss, graph ordering/cycles and live TCP requests.

## Rollback Plan
1. Trigger: accepted current-build prerequisites rejected, stale evidence
   accepted, inconsistent scope or graph ordering regression.
2. Repair shared inspection and projection; preserve fail-closed acceptance.
   Historical lifecycle and receipts are not rewritten by graph inspection.

## Versioning Decision
- Effective date: 2026-09-12; no release, commit or version bump in this checkpoint.
- Existing lifecycle values remain unchanged. Consumers must use acceptance
  fields for completion and dependency claims.
