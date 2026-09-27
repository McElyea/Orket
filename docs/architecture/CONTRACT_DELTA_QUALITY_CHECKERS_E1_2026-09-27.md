# Contract delta: truthful quality checker observations

## Summary

- Change title: Pytest marker authority and binding-aware no-op checks.
- Owner: Orket Core.
- Date: 2026-09-27.
- Affected contract: `docs/specs/QUALITY_CHECKER_CONTRACT.md`.

## Delta

The previous taxonomy scanner searched nearby prose and counted source definitions;
its missing-label count was not an inventory of absent pytest markers. The v2
report classifies actual collected items, including inherited and parameter marks,
and preserves conflicting layers and collection failures. Layer and provider/fixture
posture are separate. The no-op checker now distinguishes recognized type-only and
abstract/Protocol declarations from executable empty bodies, without filename
waivers. Both checks use the shared Git-visible inventory and refuse failed or
empty discovery. These changes repair false-positive and false-negative quality
observations; they do not establish whole-lane conformance.

## Migration Plan

1. Compatibility window: none for prose-only taxonomy authority. The evaluator
   entrypoint and existing count fields remain, but schema v2 counts pytest items.
2. Consumers retain `ok`, invalid-layer counts and collection failure fields.
   Fixtures create explicit Git repositories. Review actual test behavior when
   assigning canonical markers; repeated different layers are a conflict, not an
   override. Historical v1 observations remain historical evidence.
3. Validation gates: checker regressions include real subprocess collection and
   files, inherited/parameter classification, failed imports, Git admission,
   TYPE_CHECKING branches, binding ambiguity and executable-empty controls. Native
   repository commands remain red when real debt remains. Canonical Ruff, coverage
   thresholds, applicable Quality jobs and live runtime obligations are unchanged.

## Rollback Plan

1. Trigger: a demonstrated checker misclassification or collection regression.
2. Correct the bounded classifier with a reproducing control and rerun affected
   observations; do not reinstate prose labels as acceptance authority or hide debt.
3. No product-state migration occurs. Preserve previous diff-ledger observations
   and identify the checker version that produced each count.

## Versioning Decision

- Version bump type: next patch under the existing core release policy.
- Effective version/date: uncommitted implementation after v0.6.106, 2026-09-27.
- Downstream impact: test-governance callers must handle v2 item counts, invalid
  layers and collection failures. Product runtime contracts are unchanged.
