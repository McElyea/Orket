# Orket Docs Index

This index maps each document to a single purpose to reduce duplication.

## Start Here
1. `docs/ROADMAP.md`: roadmap entrypoint; active sequencing lives in `docs/implementation/PhasedRoadmap.md`.
2. `docs/RUNBOOK.md`: operational commands and incident handling.
3. `docs/SECURITY.md`: auth, webhook trust boundary, and security posture.
4. `docs/ARCHITECTURE.md`: runtime layering and dependency direction.
5. `docs/QUANT_SWEEP_RUNBOOK.md`: quant sweep and diagnostics workflow.

## Contracts and Specs
1. `docs/API_FRONTEND_CONTRACT.md`: API payload contracts.
2. `docs/specs/EXPLORER_SCHEMA_POLICY.md`: explorer schema policy.
3. `docs/specs/EXPLORER_FRONTIER_SCHEMA.md`: frontier artifact fields.
4. `docs/specs/EXPLORER_CONTEXT_CEILING_SCHEMA.md`: context artifact fields.
5. `docs/specs/EXPLORER_THERMAL_STABILITY_SCHEMA.md`: thermal artifact fields.
6. `docs/specs/MEMORY_CANONICALIZATION_JSON_V1.md`: canonical JSON normalization for memory determinism artifacts.
7. `docs/specs/MEMORY_DETERMINISM_TRACE_SCHEMA.md`: deterministic run trace contract.
8. `docs/specs/MEMORY_RETRIEVAL_TRACE_SCHEMA.md`: retrieval trace contract.
9. `docs/specs/MEMORY_TOOL_PROFILE_SCHEMA.md`: tool profile and fingerprint ownership contract.
10. `docs/specs/MEMORY_BUFFER_STATE_MACHINE.md`: buffered write and commit recovery state-machine contract.
11. `docs/specs/SIDECAR_PARSE_SCHEMA.md`: canonical sidecar parse schema and status contract.

## Implementation Plans
1. `docs/implementation/PhasedRoadmap.md`: canonical ordered backlog for remaining implementation work.
2. Completed implementation plan artifacts are intentionally removed when closed; use git history for archived plans.

## Engineering Policy
1. `docs/TESTING_POLICY.md`: test-lane policy (`unit`/`integration`/`acceptance`/`live`).
2. `docs/PR_REVIEW_POLICY.md`: review requirements.
3. `docs/LOCAL_CLEANUP_POLICY.md`: local artifact cleanup policy.

## Historical / Reference
1. `docs/PROJECT.md`: stable project framing.
2. `docs/VOLATILITY_BASELINE.md`: volatility baseline context.
3. `docs/architecture/`: ADR and dependency snapshots.

## Ownership Rule
If content appears in more than one doc:
1. Keep one canonical source.
2. Replace duplicates with a link.
3. Update this index when canonical ownership changes.
