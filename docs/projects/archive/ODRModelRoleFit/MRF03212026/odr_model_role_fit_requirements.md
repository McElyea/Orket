# ODR Model-Role Fit Requirements

Last updated: 2026-03-21
Status: Archived
Owner: Orket Core
Lane type: Serial ODR pair-selection experiment

## 1. Objective

Establish the bounded requirements for a serial ODR model-role fit experiment that identifies the best available local architect and reviewer combinations for requirements refinement.

This lane exists to answer a narrower question than the archived continuity lane:

**Which architect/reviewer model-role combinations produce the strongest serial ODR behavior for requirements refinement when continuity is held fixed instead of treated as the experimental variable?**

The lane must produce authority for:

1. a fixed serial pair-selection matrix,
2. a gated secondary triple round-robin matrix,
3. stable inspectability, compare, verdict, and closeout artifacts,
4. a reproducible ranking method for selecting the best pair and the best architect/reviewer candidates,
5. a truthful closeout decision that does not overclaim global ODR validity or invalidity.

## 2. Settled Background

The archived ContextContinuity lane is settled background for this experiment:

1. [docs/projects/archive/ContextContinuity/CC03212026/Closeout.md](docs/projects/archive/ContextContinuity/CC03212026/Closeout.md) showed that stronger continuity alone did not make the prior locked primary pair materially worthwhile.
2. That result is bounded evidence about the tested pair, scenarios, budgets, and thresholds. It is not authority to conclude that ODR is globally invalid.
3. The continuity question is closed for this lane. If the archived `v1_compiled_shared_state` substrate is available, reuse it as a fixed execution substrate rather than reopening control-vs-V0-vs-V1 comparison.
4. This lane is about model-role fit, not continuity-mode selection.

## 3. Decision Lock

The chosen target for this lane is:

**serial ODR model-role fit selection with frozen scenarios, frozen budgets, frozen serial order, and continuity held constant.**

The lane does not attempt to prove:

1. that ODR is universally good,
2. that ODR is universally bad,
3. that any one provider is categorically superior outside the frozen local-model setup,
4. that coder-specialized or reasoning-leak-prone models can never be useful in later sensitivity checks.

## 4. Scope

### In scope

1. a primary serial architect/reviewer pair matrix,
2. a gated secondary triple round-robin phase,
3. reuse of the ContextContinuity scenario family, locked budgets, inspectability style, and verdict discipline where practical,
4. provider resolution at bootstrap time as part of a frozen `(provider, model)` execution identity,
5. machine-readable staging artifacts for inspectability, compare, verdict, ranking, and closeout.

### Out of scope

1. reopening the continuity question as an experimental variable,
2. introducing parallel fan-out or concurrent model execution,
3. publishing results before the user approves publication,
4. bringing excluded coder or reasoning-leak-prone models into the first primary matrix,
5. changing the locked scenarios or locked budgets mid-lane without an explicit archived rationale.

## 5. Execution Rules

1. Execution is serial only. No parallel pair runs, no parallel triple runs, and no overlapping model residency.
2. The primary execution substrate is the archived `v1_compiled_shared_state` continuity path if it remains runnable. If that substrate is unavailable, the lane must block and report the exact drift rather than silently substituting a new continuity comparison.
3. The frozen scenario family is the archived ContextContinuity primary scenario set:
   1. `missing_constraint_resolved`
   2. `overfitting`
4. The locked budgets are:
   1. `5`
   2. `9`
5. The locked within-pair run order is:
   1. budget `5`
   2. budget `9`
6. The locked within-budget scenario order is:
   1. `missing_constraint_resolved`
   2. `overfitting`
7. Provider identity is part of the execution identity. Each model must be resolved to a concrete installed provider at bootstrap time and remain frozen for the full lane.
8. The first primary matrix must prefer stable general instruction models over coder-specialized or reasoning-leak-prone models.
9. The per-role call timeout must be locked in the machine-readable lane config and remain fixed for the full lane once live execution begins.

## 6. First-Pass Candidate Policy

### 6.1 Primary architect candidates

1. `llama-3.3-70b-instruct`
2. `mistralai/magistral-small-2509`
3. `gemma3:27b`
4. `Command-R:35B`
5. `qwen3.5-27b`

### 6.2 Primary reviewer candidates

1. `llama-3.3-70b-instruct`
2. `gemma3:27b`
3. `mistralai/magistral-small-2509`
4. `Command-R:35B`

### 6.3 First-pass exclusions

The following models are excluded from the first primary matrix unless explicitly reopened later as sensitivity-only checks:

1. `qwen/qwen3.5-35b-a3b`
2. `unsloth/qwen3.5-35b-a3b`
3. `deepseek-r1:32b`
4. `deepseek-coder:33B`
5. `qwen3-coder:latest`
6. `qwen2.5-coder:14b`
7. `qwen2.5-coder:7b`

## 7. Proposed Primary Pair Matrix

The primary pair matrix is fixed in this exact order:

1. `mistralai/magistral-small-2509 -> gemma3:27b`
2. `gemma3:27b -> mistralai/magistral-small-2509`
3. `llama-3.3-70b-instruct -> gemma3:27b`
4. `gemma3:27b -> llama-3.3-70b-instruct`
5. `llama-3.3-70b-instruct -> mistralai/magistral-small-2509`
6. `mistralai/magistral-small-2509 -> llama-3.3-70b-instruct`
7. `Command-R:35B -> gemma3:27b`
8. `gemma3:27b -> Command-R:35B`
9. `qwen3.5-27b -> gemma3:27b`
10. `gemma3:27b -> qwen3.5-27b`

## 8. Proposed Secondary Triple Matrix

The secondary triple phase is gated. It may begin only after the full primary pair pass is complete and the surviving top `2` or `3` pair candidates are selected under Section 11.

Preferred triple candidates:

1. `llama-3.3-70b-instruct -> gemma3:27b -> mistralai/magistral-small-2509`
2. `mistralai/magistral-small-2509 -> gemma3:27b -> llama-3.3-70b-instruct`
3. `gemma3:27b -> llama-3.3-70b-instruct -> mistralai/magistral-small-2509`

For each admitted triple candidate, both reviewer orders must be tested:

1. `architect -> reviewer A -> reviewer B`
2. `architect -> reviewer B -> reviewer A`

If a preferred triple includes a model that does not survive the pair pass, that triple is skipped and the skip reason must be recorded in the machine-readable verdict and closeout artifacts.

## 9. Exact Serial Execution Order

### 9.1 Primary pair phase

The exact serial pair order is:

1. `mistralai/magistral-small-2509 -> gemma3:27b`
2. `gemma3:27b -> mistralai/magistral-small-2509`
3. `llama-3.3-70b-instruct -> gemma3:27b`
4. `gemma3:27b -> llama-3.3-70b-instruct`
5. `llama-3.3-70b-instruct -> mistralai/magistral-small-2509`
6. `mistralai/magistral-small-2509 -> llama-3.3-70b-instruct`
7. `Command-R:35B -> gemma3:27b`
8. `gemma3:27b -> Command-R:35B`
9. `qwen3.5-27b -> gemma3:27b`
10. `gemma3:27b -> qwen3.5-27b`

For each pair, the exact serial sub-order is:

1. bootstrap and freeze `(provider, model)` identities,
2. run budget `5`,
3. run budget `9`,
4. append inspectability, compare, and verdict surfaces,
5. advance to the next pair.

### 9.2 Secondary triple phase

The secondary triple phase begins only after the pair pass is complete and ranked.

If admitted by Section 11, the exact triple order is:

1. `llama-3.3-70b-instruct -> gemma3:27b -> mistralai/magistral-small-2509`
2. `llama-3.3-70b-instruct -> mistralai/magistral-small-2509 -> gemma3:27b`
3. `mistralai/magistral-small-2509 -> gemma3:27b -> llama-3.3-70b-instruct`
4. `mistralai/magistral-small-2509 -> llama-3.3-70b-instruct -> gemma3:27b`
5. `gemma3:27b -> llama-3.3-70b-instruct -> mistralai/magistral-small-2509`
6. `gemma3:27b -> mistralai/magistral-small-2509 -> llama-3.3-70b-instruct`

Skipped triples must preserve ordinal position and emit an explicit skip record rather than collapsing the serial history.

## 10. Artifact and Verdict Surfaces

The lane must emit stable diff-ledger-backed staging artifacts under:

`benchmarks/staging/odr/model_role_fit/`

Required surfaces:

1. lane bootstrap/config snapshot:
   1. `odr_model_role_fit_lane_bootstrap.json`
2. pair-phase inspectability artifact:
   1. `odr_model_role_fit_pair_inspectability.json`
3. pair-phase compare artifact:
   1. `odr_model_role_fit_pair_compare.json`
4. pair-phase verdict/ranking artifact:
   1. `odr_model_role_fit_pair_verdict.json`
5. triple-phase inspectability artifact:
   1. `odr_model_role_fit_triple_inspectability.json`
6. triple-phase compare artifact:
   1. `odr_model_role_fit_triple_compare.json`
7. triple-phase verdict artifact:
   1. `odr_model_role_fit_triple_verdict.json`
8. final lane closeout decision artifact:
   1. `odr_model_role_fit_closeout.json`

Every scenario-run row must record:

1. `stop_reason`
2. `execution_status`
3. `rounds_consumed`
4. `median_round_active_context_size_bytes`
5. `median_round_active_context_size_tokens` when available
6. `converged`
7. `reopened_decision_count`
8. `contradiction_count`
9. `regression_count`
10. `carry_forward_integrity`
11. `median_round_latency_ms`

Inspectability surfaces must reuse the ContextContinuity style where practical:

1. loaded context artifacts,
2. role-view derivation,
3. predecessor linkage,
4. shared-state or replay references when present,
5. source-input inventories and stable hashes.

## 11. Ranking and Advancement Rules

### 11.1 Pair-phase ranking

After the full pair pass completes, rank structurally credible pairs in this exact order:

1. higher convergence rate across locked budgets,
2. lower contradiction rate,
3. lower reopened-decision rate,
4. lower regression rate,
5. lower median round latency,
6. lower median active-context size,
7. higher carry-forward integrity.

If a pair is structurally dominated by code leakage or format failure across the frozen scenario-run surface, it is ineligible for the triple phase and must be labeled `structurally_disqualified` before ranking.

If a pair cannot complete the frozen scenario-run surface because of provider or runtime failure, it is ineligible for the triple phase and must be labeled `execution_blocked` before ranking.

For this lane, `structurally_disqualified` is locked to:

1. structural stop reasons:
   1. `CODE_LEAK`
   2. `FORMAT_VIOLATION`
2. structural failure rate threshold:
   1. strictly greater than `0.5` across the frozen scenario-run surface

### 11.2 Triple-phase admission

1. Select the top `2` or `3` non-disqualified pairs only after the full pair pass completes.
2. Do not start triples until the pair pass is complete.
3. Only triples whose constituent models are represented in the surviving top `2` or `3` pairs may advance.
4. This lane locks the maximum admitted pair set for triple selection to `3`.
5. If fewer than `2` non-disqualified pairs survive, the triple phase is skipped and the skip reason is emitted in the verdict and closeout artifacts.

## 12. Closeout Decision Rule

The lane closes with the following outputs:

1. the best observed architect/reviewer pair,
2. the top `2` or `3` surviving pair candidates,
3. any admitted triple outcomes,
4. a conservative selection of best architect and best reviewer models only when the evidence supports that claim.

The closeout decision rule is:

1. choose the highest-ranked non-disqualified pair after the full pair pass and any admitted triple sensitivity checks,
2. prefer pair evidence over single-model folklore,
3. declare a single `best architect model` only if that model:
   1. appears in the top pair, and
   2. performs credibly in at least two structurally non-disqualified architect-role runs,
4. declare a single `best reviewer model` only if that model:
   1. appears in the top pair, and
   2. performs credibly in at least two structurally non-disqualified reviewer-role runs,
5. if the evidence supports only a best pair and not individually dominant role winners, report `best observed pair only` rather than overstating individual model superiority.

## 13. Non-Deception Rules

1. Do not collapse provider identity out of the recorded execution identity.
2. Do not change scenario family, budgets, or serial order after live execution begins.
3. Do not promote excluded models into the first primary matrix.
4. Do not start the triple phase early.
5. Do not use triple results to rewrite the primary pair denominator.
6. Do not conclude from a failed pair matrix that ODR is globally invalid.
