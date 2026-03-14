# Contract Delta Proposal

## Summary
- Change title: Claim E strict-compare surface narrowing to authored operator outputs
- Owner: Orket Core
- Date: 2026-03-14
- Affected contract(s): `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`, `docs/projects/archive/techdebt/DD03142026/DD03142026-deterministic-drift-requirements.md`

## Delta
- Current behavior: strict replay compare treated runtime-generated support artifacts and fresh run identity as part of the deterministic Claim E surface, so equivalent fresh runs still failed compare on `observability/runtime_events.jsonl`, `verification/runtime_verification.json`, interpreter cache artifacts, and `session_id`-derived digests even when authored operator outputs matched.
- Proposed behavior: strict replay compare keeps authored workspace outputs and stable scaffold files in scope, excludes the runtime-generated support artifacts listed above, and ignores fresh `session_id` differences when all governed replay state and in-scope artifacts match.
- Why this break is required now: the broader compare claim was not supported by live evidence and created false-red deterministic drift after the authored operator surface had converged.

## Migration Plan
1. Compatibility window: immediate on merge; this is a truthful narrowing to the shipped deterministic operator surface.
2. Migration steps:
   - compare fresh live runs on authored outputs and stable scaffold files only
   - treat `observability/runtime_events.jsonl`, `verification/runtime_verification.json`, and `**/__pycache__/*.pyc` as runtime-generated support artifacts outside strict operator scope
   - ignore fresh `session_id` identity when strict compare state is otherwise equal
3. Validation gates:
   - comparator regression tests for fresh session identity
   - live strict compares across three fresh runs with all pairwise filtered comparisons passing
   - replay and provider preflight remaining green

## Rollback Plan
1. Rollback trigger: a future operator contract explicitly promotes any excluded support artifact into the deterministic operator surface or requires run-identity equality.
2. Rollback steps:
   - restore the broader compare scope only with matching runtime implementation and live proof
   - revert the comparator/session-identity rule if run identity becomes part of the governed state
   - publish a new proof packet showing the widened contract truthfully
3. Data/state recovery notes: no data migration is required because the change narrows compare semantics to already-emitted artifacts.

## Versioning Decision
- Version bump type: none for this docs/runtime-proof delta by itself
- Effective version/date: 2026-03-14
- Downstream impact: operators should treat authored outputs as the deterministic Claim E surface and should not interpret runtime support artifact churn or fresh run ids as operator-visible drift.
