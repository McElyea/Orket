# ODR Loop-Shape Hardening Implementation Plan

Last updated: 2026-03-22
Status: Archived
Owner: Orket Core

Background authority:

1. `docs/projects/archive/ODRRoleFitFollowup/RFU03222026/Closeout.md`
2. `docs/projects/archive/ODRModelRoleFit/MRF03212026/Closeout.md`
3. `docs/projects/archive/ContextContinuity/CC03212026/Closeout.md`
4. `docs/projects/archive/ODRRoundCapProbe/RCP03222026/Closeout.md`

## Objective

Run the next bounded ODR follow-up on one fixed local pair:

1. keep `Command-R:35B -> gemma3:27b` fixed,
2. hold scenarios and budgets constant,
3. change loop and prompt protocol variables instead of model selection,
4. measure whether stricter issue accounting and scope-growth controls improve convergence without breaking the pair's current continuity discipline.

## Scope Lock

1. Treat the archived ContextContinuity and model-role-fit lanes as settled bounded background evidence.
2. Treat `Command-R:35B -> gemma3:27b` as the fixed continuation pair for this lane.
3. Keep execution serial only.
4. Keep the locked scenario set:
   1. `missing_constraint_resolved`
   2. `overfitting`
5. Keep the locked budgets:
   1. `5`
   2. `9`
6. Do not fan back out to more architect or reviewer models in this lane.
7. Start with prompt and loop-shape hardening before deeper kernel rewrites.
8. Keep all rerunnable evidence in `benchmarks/staging/`.

## Proposed Execution Slices

### LSH-IMP-00: Authority Freeze and Harness Wiring

Objective:

1. freeze the fixed pair, scenario set, budgets, and artifact paths in machine-readable form,
2. capture the first-pass loop-shape hardening policy in the lane config,
3. reuse the existing staged pair-compare/verdict surfaces where practical.

### LSH-IMP-01: Issue-Accounting and Scope-Growth Hardening

Objective:

1. add stricter prompt-level issue accounting,
2. limit scope growth unless tied to cited unresolved issues or regressions,
3. tighten allowed patch behavior without reopening the archived model matrix.

### LSH-IMP-02: Fixed-Pair Live Rerun

Objective:

1. rerun `Command-R:35B -> gemma3:27b` under the hardened loop shape,
2. emit bootstrap, inspectability, compare, verdict, and closeout artifacts,
3. compare the new stop behavior to the archived reviewer-fit follow-up evidence.

### LSH-IMP-03: Follow-On Hardening Decision

Objective:

1. decide whether the next change should be another bounded protocol adjustment, a deeper state/identity change, or lane closeout,
2. avoid reopening model expansion unless the hardened fixed pair still leaves protocol evidence ambiguous.

## Success Criteria

The lane is ready for execution only when:

1. the roadmap points to this plan,
2. the fixed pair and protocol policy are frozen in machine-readable form,
3. the follow-up scope is clearly loop-shape hardening rather than pair-matrix expansion.

The lane is complete only when:

1. the hardened fixed-pair run has been executed at both locked budgets,
2. the staging artifacts truthfully report whether stop behavior improved, regressed, or stayed flat,
3. the lane closes or advances with an explicit bounded next-step decision.

## Current Execution Status

1. `LSH-IMP-00` is completed. The fixed pair, locked budgets, scenario set, artifact paths, and first-pass protocol hardening rules are frozen in [odr_loop_shape_hardening_lane_config.json](docs/projects/archive/ODRLoopShapeHardening/LSH03222026/odr_loop_shape_hardening_lane_config.json) and [odr_loop_shape_hardening_matrix_registry.json](docs/projects/archive/ODRLoopShapeHardening/LSH03222026/odr_loop_shape_hardening_matrix_registry.json).
2. `LSH-IMP-01` is completed for the first-pass prompt-policy change set. The architect and auditor prompt contracts now accept lane-scoped hardening rules, and the live runner snapshots them into emitted artifacts.
3. `LSH-IMP-02` has completed its first fixed-pair live rerun. The current result is negative: `Command-R:35B -> gemma3:27b` still converged on `0/4` scenario-runs across the locked budgets, with `MAX_ROUNDS`, `INVALID_CONVERGENCE`, and one `CODE_LEAK` stop. See the staging artifacts under `benchmarks/staging/odr/loop_shape_hardening/`.
4. `LSH-IMP-03` is completed. The later archived round-cap probe showed one `5`-round truncation was too low, but the hardened loop still did not deliver stable promotable improvement, so the lane closes with bounded non-promotion evidence rather than another prompt-only hardening pass.
