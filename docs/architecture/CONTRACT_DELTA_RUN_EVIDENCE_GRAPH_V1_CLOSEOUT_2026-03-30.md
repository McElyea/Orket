# Run Evidence Graph V1 Contract Delta

## Summary
- Change title: Run-evidence graph v1 durable contract publication and Graph lane closeout
- Owner: Orket Core
- Date: 2026-03-30
- Affected contract(s): `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`

## Delta
- Current behavior: Run-evidence graph requirements and execution sequencing lived under an active Graph project lane, so the durable contract, archive record, roadmap posture, and authority map could drift once implementation and proof landed.
- Proposed behavior: promote `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` as the active durable contract, keep completed implementation and proof in the archived Graph lane record, and make the roadmap and authority map reflect maintenance-only posture instead of an active Graph lane.
- Why this break is required now: leaving a completed implementation lane active after structural, integration, and live proof would weaken contract discoverability and create avoidable drift between the shipped operator path, emitted artifact family, archive evidence, and active documentation.

## Migration Plan
1. Compatibility window: none; this is additive durable-contract publication plus same-change lane closeout.
2. Migration steps:
   1. publish `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` as the active durable contract authority
   2. archive the Graph lane requirements, history, and implementation plan under `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/`
   3. remove the completed Graph lane from `docs/ROADMAP.md` and return the roadmap to maintenance-only posture
   4. sync `CURRENT_AUTHORITY.md` and `docs/README.md` to the promoted spec and active operator path
3. Validation gates:
   1. run-evidence graph structural, integration, and live proof remain green
   2. `python scripts/governance/check_docs_project_hygiene.py` passes after the archive move
   3. the active spec, roadmap, and authority map all point to the same durable surface

## Rollback Plan
1. Rollback trigger: docs hygiene fails, archive relocation leaves stale active references, or the promoted contract cannot be supported by the implemented runtime path.
2. Rollback steps:
   1. restore the Graph lane to active `docs/projects/` status
   2. restore the active Graph roadmap entry if additional implementation or proof work is required
   3. remove or revise the durable contract and authority references if the shipped operator path is not supportable
3. Data/state recovery notes: the change is documentation-, test-, and runtime-surface-level only; no durable data migration is required.

## Versioning Decision
- Version bump type: additive durable-contract publication and same-change lane closeout
- Effective version/date: 2026-03-30
- Downstream impact: run-evidence graph readers should use `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` for the active contract and `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/CLOSEOUT.md` for completed-lane proof and history.
