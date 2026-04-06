# Contract Delta: ProductFlow operator review package contract freeze

## Summary
- Change title: ProductFlow governed `write_file` durable spec publication and active-lane sync
- Owner: Orket Core
- Date: 2026-04-05
- Affected contract(s): `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`, `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`

## Delta
- Current behavior: ProductFlow lane authority lived only in active lane docs, the review and replay wrappers did not have durable spec surfaces, and the original lane plan assumed `run_summary.json` would declare the governed `run_id` directly.
- Proposed behavior: promote durable ProductFlow review-package and walkthrough specs, freeze the admitted resolver witness as unique `approval.control_plane_target_ref == <run_id>` plus validated `runs/<session_id>/run_summary.json`, and close the lane only after the full Workstream 4 proof bundle is complete.
- Why this break is required now: the shipped ProductFlow wrapper contract and resolver witness are specific enough to freeze durably, and lane closeout is truthful only once the same-run live, review-package, replay-review, and roadmap/archive closeout bundle is complete.

## Migration Plan
1. Compatibility window: none; this is same-change durable-contract publication and active-lane contract sync.
2. Migration steps:
   1. publish `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`
   2. publish `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`
   3. archive the completed ProductFlow plan and requirements under `docs/projects/archive/ProductFlow/PF04052026-LANE-CLOSEOUT/` once the remaining proof bundle is complete
   4. sync `CURRENT_AUTHORITY.md`, `docs/README.md`, and `docs/ROADMAP.md` to the promoted ProductFlow surfaces without claiming lane closeout
3. Validation gates:
   1. `ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py`
   2. `python scripts/productflow/build_operator_review_package.py --run-id <run_id>`
   3. `python scripts/productflow/run_replay_review.py --run-id <run_id>`
   4. `python scripts/governance/record_truthful_runtime_packet1_live_proof.py`
   5. `python scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py`
   6. `python scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py`
   7. `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger: the promoted ProductFlow specs no longer match the shipped wrapper behavior or the active-lane docs drift away from the admitted ProductFlow contract surfaces.
2. Rollback steps:
   1. revise or remove the promoted ProductFlow spec surfaces
   2. keep the roadmap and active ProductFlow plan aligned to the last proven behavior
   3. remove or revise the promoted ProductFlow spec references in `CURRENT_AUTHORITY.md` and `docs/README.md` if the wrapper contract changes
3. Data/state recovery notes: this is a docs-and-proof-surface delta only; no durable runtime data migration is required.

## Versioning Decision
- Version bump type: additive durable-contract publication and active-lane contract freeze
- Effective version/date: 2026-04-05
- Downstream impact: ProductFlow operators should now use the promoted specs for the shipped wrapper and resolver contract, with lane history and closeout archived under `docs/projects/archive/ProductFlow/PF04052026-LANE-CLOSEOUT/`.
