# ODR Model-Role Fit Implementation Plan

Last updated: 2026-03-21
Status: Archived
Owner: Orket Core

Requirements authority: `docs/projects/archive/ODRModelRoleFit/MRF03212026/odr_model_role_fit_requirements.md`

## Objective

Provide the canonical execution path for the bounded ODR model-role fit experiment.

## Scope Lock

1. The requirements authority is accepted and controls this lane.
2. Treat [docs/projects/archive/ContextContinuity/CC03212026/Closeout.md](docs/projects/archive/ContextContinuity/CC03212026/Closeout.md) as settled background, not as an open lane.
3. Keep execution serial only.
4. Reuse the archived `v1_compiled_shared_state` substrate if it remains runnable; do not reopen the continuity experiment here.
5. Keep the primary pair matrix, secondary triple matrix, locked budgets, locked scenarios, and artifact surfaces exactly aligned with the requirements authority unless an explicit archived rationale changes them.

## Proposed Execution Slices

### MRF-IMP-00: Bootstrap and Authority Freeze

Objective:

1. Freeze installed `(provider, model)` identities for the candidate pool.
2. Commit the machine-readable lane config, pair/triple registry, and canonical staging output paths.
3. Lock the primary pair serial order, locked budgets, scenario family, and per-role call timeout in code-readable form.

### MRF-IMP-01: Harness Reuse and Artifact Wiring

Objective:

1. Reuse the archived serial ODR continuity substrate where practical.
2. Adapt inspectability, compare, verdict, and closeout surfaces for pair-selection instead of continuity selection.
3. Preserve the ContextContinuity metric vocabulary and scenario-run accounting surfaces where practical.
4. Distinguish experimental outcome failure from provider/runtime blockers in the emitted scenario-run artifacts and selection logic.

### MRF-IMP-02: Primary Pair Pass

Objective:

1. Run the full primary pair matrix in the locked serial order.
2. Emit inspectability, compare, and verdict artifacts for every pair at both locked budgets.
3. Rank pairs only after the full pass completes.

### MRF-IMP-03: Gated Triple Pass

Objective:

1. Select the top `2` or `3` surviving pairs under the locked ranking rule.
2. Run only the admitted triples in the locked serial order.
3. Emit triple inspectability, compare, and verdict artifacts.

### MRF-IMP-04: Closeout and Selection

Objective:

1. Produce the final closeout artifact.
2. Select the best observed pair.
3. Select best architect and best reviewer models only if the requirements authority threshold for those claims is satisfied.
4. Close the lane without overclaiming global ODR validity or invalidity.

## Success Criteria

The lane is ready for execution only when:

1. the requirements authority is accepted,
2. a machine-readable lane config exists,
3. canonical staging artifact paths are locked,
4. serial provider/model identity freeze is implemented,
5. the pair and triple gates are mechanically reproducible.

The lane is complete only when:

1. the full primary pair pass has run,
2. any admitted triple pass has run,
3. final compare, verdict, and closeout artifacts exist,
4. the closeout decision selects the best observed pair and, where justified, the best architect and reviewer models,
5. roadmap and project-index cleanup happen in the same closeout change.

## Outcome

The lane completed the frozen serial pair pass, the gated triple pass, and the final closeout artifact. See [Closeout.md](docs/projects/archive/ODRModelRoleFit/MRF03212026/Closeout.md).
