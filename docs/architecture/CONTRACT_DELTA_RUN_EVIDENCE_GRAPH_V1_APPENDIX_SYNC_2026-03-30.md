# Run Evidence Graph V1 Contract Delta

## Summary
- Change title: Run-evidence graph v1 Appendix A post-closeout authority sync
- Owner: Orket Core
- Date: 2026-03-30
- Affected contract(s): `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`

## Delta
- Current behavior: the active durable run-evidence graph contract still contained four Appendix A posture lines that spoke as if the Graphs requirements-hardening lane were active, even though that lane had already been closed and archived on 2026-03-30.
- Proposed behavior: keep Appendix A non-normative and unchanged in substance, but rewrite those posture lines so they truthfully reference the archived 2026-03-30 Graphs lane instead of an active lane.
- Why this break is required now: leaving active-lane wording in the active spec after closeout creates avoidable authority drift and makes the Graphs archive posture look unresolved when it is already closed.

## Migration Plan
1. Compatibility window: none; this is a documentation-only authority sync with no runtime or schema delta.
2. Migration steps:
   1. rewrite the stale Appendix A posture lines in `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
   2. keep the archived Graphs packet as the historical source for the filtered-view decisions
   3. leave the active roadmap in maintenance-only posture because no new Graphs implementation lane is reopened by this sync
3. Validation gates:
   1. `python scripts/governance/check_docs_project_hygiene.py` passes
   2. targeted run-evidence graph tests remain green
   3. no active doc still describes the Graphs lane as active

## Rollback Plan
1. Rollback trigger: the wording change introduces new drift, or the active spec now misstates the Graphs archive posture.
2. Rollback steps:
   1. restore the prior Appendix A wording
   2. re-evaluate whether a new explicit Graphs roadmap lane is actually required
3. Data/state recovery notes: no durable data, schema, or runtime behavior is affected.

## Versioning Decision
- Version bump type: non-normative authority sync
- Effective version/date: 2026-03-30
- Downstream impact: readers of `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` now get a truthful archived-lane posture without implying that Graphs remains active.
