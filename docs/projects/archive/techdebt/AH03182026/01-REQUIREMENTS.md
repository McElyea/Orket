# AH03182026 Phase 2 Auditability Hardening Requirements

Last updated: 2026-03-18
Status: Archived (requirements satisfied)
Owner: Orket Core
Lane type: Techdebt auditability hardening

Archive note:
1. Completed and archived on 2026-03-18.
2. Closeout authority: [docs/projects/archive/techdebt/AH03182026/Closeout.md](docs/projects/archive/techdebt/AH03182026/Closeout.md)

## Purpose

Define the bounded implementation contract for Phase 2 in [docs/projects/future/game-plan.md](docs/projects/future/game-plan.md).

This lane exists to make the Phase 2 auditability claim executable without widening into a general runtime rewrite.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/ARCHITECTURE.md`
6. [docs/projects/future/game-plan.md](docs/projects/future/game-plan.md)
7. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md)
8. [docs/projects/archive/techdebt/RG03182026/Closeout.md](docs/projects/archive/techdebt/RG03182026/Closeout.md)
9. [scripts/probes/probe_support.py](scripts/probes/probe_support.py)
10. [orket/runtime/run_summary.py](orket/runtime/run_summary.py)
11. [orket/orchestration/engine.py](orket/orchestration/engine.py)
12. [orket/kernel/v1/canon.py](orket/kernel/v1/canon.py)
13. [scripts/replay/replay_comparator.py](scripts/replay/replay_comparator.py)

## Current Truth

1. Phase 1 and RG03182026 established the remediated cards and explicit ODR surfaces that Phase 2 must audit.
2. Before this lane, Phase 2 in the future game plan defined the problem but did not extract one durable MAR contract into `docs/specs/`.
3. `run_summary.json` and per-turn observability artifacts already exist, but no canonical script currently determines whether a run is MAR-complete.
4. `OrchestrationEngine.replay_turn()` can read persisted turn artifacts, but it is a diagnostic helper, not a canonical audit operator with replay verdict output.
5. `orket.kernel.v1.canon.first_diff_path()` already exists for structural diff localization, but there is no Phase 2 operator that applies it to equivalent-run audit records.
6. Stability cannot be truthfully claimed from a single run, even when all single-run artifacts are present.
7. Phase 3 workload claims should remain blocked until this lane closes with explicit auditability proof.

## Closeout Result

Resolved on 2026-03-18.

1. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md) is active, and phase-scoped closeout authority now lives in [docs/projects/archive/techdebt/AH03182026/Closeout.md](docs/projects/archive/techdebt/AH03182026/Closeout.md).
2. `scripts/audit/verify_run_completeness.py`, `scripts/audit/compare_two_runs.py`, and `scripts/audit/replay_turn.py` exist as canonical audit operators with stable output paths and diff-ledger writes.
3. Live Phase 2 proof produced `mar_complete=true` for one completed cards run and one ODR-enabled cards run.
4. S-02 reported a governed equivalent-run verdict of `stable` over a canonical two-run pair while excluding fresh identity differences only.
5. S-03 reported a truthful structural replay verdict of `diverged`; replay divergence was surfaced explicitly instead of being reclassified as stable or soft success.
6. Phase 3 is no longer blocked on missing Phase 2 audit operators, but stability claims remain scoped to actual S-02 and S-03 evidence.

## Resolution Goal

This lane is complete only when Orket can truthfully do all of the following:

1. determine whether a completed run is MAR-complete
2. determine whether a completed run is replay-ready
3. compare two equivalent runs at the governed MAR surface and report the first material divergence
4. replay one preserved turn and report whether the reproduced output structurally matches the original
5. say `not_evaluable` instead of claiming stability when comparative proof is absent

## Scope

In scope:

1. MAR v1 adoption and doc authority cleanup
2. `scripts/audit/verify_run_completeness.py`
3. `scripts/audit/compare_two_runs.py`
4. `scripts/audit/replay_turn.py`
5. minimal runtime artifact additions only if required to satisfy MAR v1
6. targeted tests and live proof needed for these audit operators

Out of scope:

1. broad orchestrator or cards-engine redesign unrelated to MAR evidence
2. new workload claims beyond auditability hardening
3. claiming semantic equivalence based only on a fuzzy or advisory comparator
4. making ODR the default cards path

## MAR Requirements

1. MAR authority lives in [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md).
2. This lane must not invent a second competing MAR checklist in scripts or test fixtures.
3. If current runtime artifacts are insufficient for MAR v1, the lane may add the smallest truthful runtime artifact needed to satisfy the spec.
4. A single run may prove `mar_complete` and `replay_ready`, but stability must remain `not_evaluable` until comparative evidence exists.
5. Any advisory semantic-equivalence layer must remain additive and must not replace the required structural verdict.

## Script Requirements

### S-01: `verify_run_completeness.py`

1. The script must accept a run identity and workspace root sufficient to locate `runs/<session_id>/run_summary.json` and the associated observability tree.
2. The script must evaluate each MAR evidence group separately:
   1. run outcome
   2. turn capture
   3. authored output
   4. contract verdict
   5. stability evidence
3. The script must report:
   1. `mar_complete`
   2. `replay_ready`
   3. `stability_status`
   4. specific missing artifacts or missing evidence groups
4. The script must not infer missing authored outputs or verdict artifacts from terminal status alone.
5. Default rerunnable JSON output path:
   1. `benchmarks/results/audit/verify_run_completeness.json`

### S-02: `compare_two_runs.py`

1. The script must accept two equivalent runs and fail closed when the required inputs to compare them are missing.
2. The compare surface for this lane is the MAR surface only:
   1. run summary
   2. authoritative authored outputs
   3. per-turn input/output artifacts
   4. task-specific verdict artifacts
3. The script must distinguish:
   1. evidence missing
   2. in-scope divergence
   3. excluded fresh identity differences
4. JSON-structured surfaces must report the first governed divergence using `orket.kernel.v1.canon.first_diff_path()`.
5. Default rerunnable JSON output path:
   1. `benchmarks/results/audit/compare_two_runs.json`

### S-03: `replay_turn.py`

1. The script must accept `session_id`, `issue_id`, and `turn_index`, with optional `role` selection.
2. The script must use persisted turn artifacts as the replay source of truth.
3. The script must emit a structural verdict against the original `model_response.txt`.
4. If an advisory semantic verdict is added, the report must still include the structural verdict as the authoritative result.
5. Environment or provider failure during replay must be recorded explicitly as `blocked`; it must not be treated as a replay success.
6. Default rerunnable JSON output path:
   1. `benchmarks/results/audit/replay_turn.json`

## Testing and Verification Requirements

### Structural Proof

1. Add or update targeted tests for:
   1. MAR evidence-group classification
   2. missing-artifact reporting for S-01
   3. compare-surface exclusions and first-diff reporting for S-02
   4. replay-turn artifact loading and structural verdict reporting for S-03
2. Each new or modified test must be labeled as `unit`, `contract`, `integration`, or `end-to-end`.
3. Mock-heavy tests are not sufficient as the only proof for live behavior claims.

### Live Proof

1. Non-sandbox live proof for this lane must set `ORKET_DISABLE_SANDBOX=1`.
2. Canonical live proof must include:
   1. provider preflight for the selected local model
   2. at least two equivalent cards runs suitable for S-02 comparison
   3. one MAR completeness check over a completed cards run
   4. one MAR completeness check over an ODR-enabled cards run
   5. one replay-turn execution against a preserved turn from a completed run
3. If live replay or equivalent-run compare is blocked by environment constraints, the blocker must be reported exactly and the lane must not be closed as if stability were proven.

## Conclusive Gate

This lane is conclusive only when all of the following are true:

1. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md) is active and referenced from the future game plan plus the active techdebt plan.
2. S-01, S-02, and S-03 exist as canonical scripts with stable default output paths and diff-ledger writes.
3. At least one completed cards run and one ODR-enabled cards run evaluate as `mar_complete=true`.
4. S-02 reports a governed compare result over an equivalent-run pair instead of leaving determinism as an untested claim.
5. S-03 reports a structural replay verdict or an explicit environment blocker.
6. `python scripts/governance/check_docs_project_hygiene.py` passes.

## Residual Truth Rule

If the lane cannot produce comparative replay or equivalent-run proof without widening scope unsafely:

1. keep Phase 3 blocked on this closure gate
2. report `stability_status=not_evaluable` or `blocked`
3. do not claim determinism beyond what the comparative evidence actually supports
