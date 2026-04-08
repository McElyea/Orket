# Minimum Auditable Record V1

Last updated: 2026-04-08
Status: Active
Owner: Orket Core
Phase authority: `docs/projects/archive/techdebt/AH03182026/Closeout.md`

## 1. Objective

Define the smallest authoritative evidence set required to answer, for a completed Orket run:

1. what input was given to the model
2. what the model produced
3. whether the output met the task contract
4. whether the observed outcome is stable or not yet proven stable

The Minimum Auditable Record (MAR) is an evidence contract, not a success claim.

## 2. Current Bounded Scope

This contract currently governs the remediated cards and explicit ODR surfaces advanced by Phase 1 and RG03182026:

1. cards runs emitting `run_summary.json`
2. per-turn observability directories under `observability/<session_id>/`
3. cards support-verification artifacts such as:
   1. `agent_output/verification/runtime_verification.json`
   2. `agent_output/verification/runtime_verification_index.json`
   3. per-record verifier artifacts under `agent_output/verification/runtime_verifier_records/`
4. explicit ODR refinement artifacts referenced from cards run summary via `odr_artifact_path`

Out of scope for MAR v1:

1. protocol replay campaign output contracts
2. workload scoring or quality ranking beyond auditability
3. fuzzy semantic-equivalence claims that are not paired with a separately named structural verdict

## 3. Truth Model

1. MAR completeness is evaluated per completed run.
2. Missing required evidence must be reported explicitly; it must not be inferred or treated as implicitly green.
3. Single-run evidence can answer questions 1 through 3 when the required artifacts are present.
4. Single-run evidence cannot by itself prove stability. A single run may be `replay_ready`, but stability remains `not_evaluable` until a second equivalent run or replay comparison exists.
5. A script or report may state `stable` only when comparative evidence exists and the governed compare surface shows no in-scope divergence.

Canonical Phase 2 status terms:

1. `mar_complete`
2. `replay_ready`
3. `stability_status=stable|diverged|not_evaluable|blocked`

## 4. Canonical Evidence Groups

### 4.1 Run Outcome Group

Required artifact:

1. `runs/<session_id>/run_summary.json`

Minimum required fields:

1. `run_id`
2. `status`
3. `artifact_ids`
4. `failure_reason`

Conditionally required additive fields:

1. cards runs must expose `stop_reason`
2. cards runs using explicit profile routing must expose `execution_profile`
3. ODR-enabled cards runs must expose:
   1. `odr_active`
   2. `odr_artifact_path`
   3. `odr_stop_reason`
   4. `odr_valid`
   5. `odr_pending_decisions`

### 4.2 Turn Capture Group

For every persisted model turn under `observability/<session_id>/<issue_id>/<turn_dir>/`, the following artifacts are required:

1. `messages.json`
2. `model_response.txt`
3. `checkpoint.json`

Conditionally required:

1. `parsed_tool_calls.json` is required when tool parsing was attempted or tool-mode execution was expected for that turn

This group answers:

1. what input was given to the model
2. what raw output the model produced

### 4.3 Authored Output Group

Every operator-facing output named as authoritative by the run must exist at its recorded workspace-relative path.

Current bounded examples:

1. cards output files under `agent_output/`
2. explicit ODR refinement artifacts referenced by `run_summary.odr_artifact_path`

The MAR is incomplete if run-summary or verification surfaces claim an authored output that is absent on disk.

Support verification artifacts do not satisfy the Authored Output Group unless the governing run contract explicitly says the verification artifact is itself the operator-facing product.

### 4.4 Contract Verdict Group

At least one authoritative contract-verdict surface must exist so a reviewer can evaluate whether the run met its task contract.

Current allowed surfaces:

1. cards latest runtime-verification support artifact at `agent_output/verification/runtime_verification.json`, provided it records:
   1. `artifact_role=support_verification_evidence`
   2. `artifact_authority=support_only`
   3. `authored_output=false`
   4. `overall_evidence_class`
   5. `evidence_summary.syntax_only`
   6. `evidence_summary.command_execution`
   7. `evidence_summary.behavioral_verification`
   8. `evidence_summary.not_evaluated`
   9. `provenance.run_id`
   10. `provenance.issue_id`
   11. `provenance.turn_index`
   12. `provenance.retry_count`
   13. `provenance.record_id`
   14. `provenance.recorded_at`
   15. `history.index_path`
   16. `history.record_path`
2. explicit ODR refinement artifact referenced by `run_summary.odr_artifact_path`, provided it records:
   1. `history_rounds`
   2. `odr_stop_reason`
   3. `odr_valid`
   4. `odr_pending_decisions`

`run_summary.json` remains required, but run summary alone is not sufficient for MAR question 3 when no task-specific verdict artifact exists.

`runtime_verification.json` is a support-verification artifact, not an authored output.
Its fixed latest path is allowed only because the verifier now preserves materially distinct history in `runtime_verification_index.json` and per-record artifacts under `runtime_verifier_records/`.

### 4.5 Stability Evidence Group

`replay_ready` requires:

1. `mar_complete`
2. turn capture artifacts present for every persisted model turn

`stability_status=stable|diverged` requires one of:

1. a second equivalent run and a governed compare artifact over the MAR surface
2. a replay artifact that re-executes the preserved turn input and records the compare verdict against the original output

Without one of those comparative proofs, stability must remain `not_evaluable`.

## 5. Canonical Audit Questions Mapped to Evidence

1. Input given to the model:
   1. `messages.json`
   2. `checkpoint.json`
2. Model output:
   1. `model_response.txt`
   2. `parsed_tool_calls.json` when applicable
3. Contract satisfaction:
   1. `run_summary.json`
   2. task-specific verdict artifact from the Contract Verdict Group
   3. authoritative authored outputs from the Authored Output Group
4. Stability:
   1. compare artifact across two equivalent runs, or
   2. replay artifact comparing a reproduced turn to the original preserved output

## 6. Operator Surfaces Required by Phase 2

Phase 2 implementation must provide these canonical scripts:

1. `scripts/audit/verify_run_completeness.py`
   1. default output: `benchmarks/results/audit/verify_run_completeness.json`
   2. responsibility: evaluate MAR evidence groups and report missing items
2. `scripts/audit/compare_two_runs.py`
   1. default output: `benchmarks/results/audit/compare_two_runs.json`
   2. responsibility: compare two equivalent MAR-complete runs and report the first governed divergence
3. `scripts/audit/replay_turn.py`
   1. default output: `benchmarks/results/audit/replay_turn.json`
   2. responsibility: replay one preserved turn and record structural compare verdicts against the original output

All rerunnable JSON outputs for these scripts must use the canonical diff-ledger writer.

## 7. Failure Semantics

1. Missing required evidence yields `mar_complete=false`.
2. Comparative proof requested without sufficient evidence yields `stability_status=not_evaluable`.
3. Environment or provider failure during replay yields `stability_status=blocked`; it must not be reported as stability success.
4. Any future advisory semantic-equivalence layer must remain additive and must not replace the structural verdict required by MAR v1.
