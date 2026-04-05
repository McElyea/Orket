# Prompt Reforger Gemma Tool-Use Implementation Plan

Owner: Orket Core
Status: Paused / Checkpointed
Last updated: 2026-04-04

## 1. Purpose

This lane turns the recent Prompt Reforger model-selection discussion into an executable active plan.

The focus of this lane is not generic code generation.
The focus is tool-usage prompt reforging:

- rewrite prompts so local models call admitted tools correctly,
- measure those prompts against fixed tool-call acceptance slices,
- keep runtime truth in Orket contracts and validators rather than in model preference.

This lane continues the Prompt Reforger service lineage proved in Phase 0, but narrows the next active execution target to Gemma-family tool-use compatibility.

Phase 0 archive authority remains:

- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/CLOSEOUT.md`
- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/FuturePhases.md`

The durable generic service contract remains:

- `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`

## 2. Governing Decisions

The following decisions are active for this lane unless the roadmap is explicitly changed.

1. The source of truth for Prompt Reforger remains Orket contracts, validators, challenge receipts, and measured run artifacts. No model becomes authority.
2. This lane uses an all-Gemma execution strategy for the first live tool-use slice.
3. `gemma-3-12b-it-qat` is the quality-oriented primary target model for prompt reforging runs when the local runtime can actually host it.
4. `gemma-3-4b-it-qat` is the portability target and must remain in scope because the lane is intended to stay usable for operators with smaller GPUs such as a 3070 Ti class machine.
5. `FunctionGemma 270m` is the first tool-call conformance judge for this lane and is treated as the fast canary for tool-call formatting and argument-shape correctness.
6. `FunctionGemma` should default to `Q8_0` for the judge role. Smaller quants such as `Q4_0` are degradation tests, not the primary judge.
7. `Qwen2.5-7B-Instruct` is not part of the core lane architecture. It may be introduced later only as an explicit cross-family baseline if the lane needs anti-overfitting evidence.
8. Gemma 4 remains deferred and is not part of this active lane.

## 3. Admitted Model Surfaces

### Primary Gemma-family targets

1. Quality target:
   - Hugging Face / LM Studio family id: `google/gemma-3-12b-it-qat`
2. Portability target:
   - Hugging Face / LM Studio family id: `google/gemma-3-4b-it-qat`

### Tool-use judge

1. Canonical underlying model:
   - `google/functiongemma-270m-it`
2. Ollama model name:
   - `functiongemma`
3. LM Studio hub family id:
   - `google/functiongemma-270m`
4. Preferred quant for judgment:
   - `Q8_0`

## 4. Lane Objective

This lane is complete only when all of the following are true:

1. Prompt Reforger can run a fixed tool-use prompt-reforge loop against Gemma-family targets.
2. The loop uses `FunctionGemma` as a tool-call conformance judge for the first live slice.
3. The same lane proves a portability path on `gemma-3-4b-it-qat`.
4. The lane records turns, preconditions, postconditions, and exact accepted or rejected tool calls for each exercised proof slice.
5. The lane does not confuse model preference with runtime authority.
6. The lane truthfully records when `gemma-3-12b-it-qat` is unavailable or too heavy for the current machine and still allows execution on the portability target.

### Current checkpoint as of 2026-04-04

1. Workstream 0 is complete. Runtime inventory is frozen at `python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_inventory.py` and the canonical live artifact is `benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json`.
2. Workstream 1 is complete for the frozen bootstrap slice. The bounded corpus, judge protocol, and structural scorer are frozen at `docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json`, `docs/projects/PromptReforgerToolCompatibility/FUNCTIONGEMMA_TOOL_CALL_JUDGE_PROTOCOL.md`, and `python scripts/prompt_lab/score_prompt_reforger_gemma_tool_use_corpus.py --run-summary <run_summary> --observability-root <observability_root>`.
3. Workstream 2 is complete for the bounded advisory path. The canonical live judge command is `python scripts/prompt_lab/run_functiongemma_tool_call_judge.py --score-report <score_report> --inventory benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json`, and the current live artifact `benchmarks/staging/General/prompt_reforger_gemma_tool_use_judge.json` records `observed_path=fallback`, `observed_result=success`, and `inconclusive_count=0` after routing the advisory judge through one admitted `emit_judgment` native tool contract. Ollama `functiongemma:latest` is now inventory-visible but remains all-inconclusive on this machine, so the live judge command truthfully falls back to LM Studio `functiongemma-270m-it`.
4. Workstream 3 is partial. The canonical bounded cycle command is `python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_cycle.py --targets both --runs 1`, and the current live artifact `benchmarks/staging/General/prompt_reforger_gemma_tool_use_cycle.json` records that `gemma-3-12b-it-qat` baseline still clears the frozen five-slice corpus while the bounded prompt candidates do not beat baseline.
5. Workstream 4 is partial. The same 2026-04-04 cycle artifact records that `gemma-3-4b-it-qat` remains executable but still only reaches `accepted_slices=2` of `5`, with `partial_slices=1` and `not_exercised_slices=2`.
6. Workstream 5 remains frozen to `pause_lane_with_blockers`. The lane stays paused because the bounded Gemma-only portability path did not clear the frozen corpus. The judge blocker is no longer the gating blocker for this lane.
7. Exploratory prompt-only variants and a temporary non-canonical Gemma output-budget override were evaluated on 2026-04-04, but neither produced a truthful portability clear under canonical authority. Do not treat those exploratory runs as lane completion.
8. A bounded guide-model comparison harness now exists at `python scripts/prompt_lab/run_prompt_reforger_guide_model_comparison.py --targets portability --runs 1 --guide-spec "<label>|<provider>|<model>[|<base_url>]"`. It keeps the Gemma target lane fixed and compares guide models by generated prompt-candidate quality from the frozen corpus scoreboards. It does not change the lane completion criteria and does not silently replace the paused `gemma-3-4b-it-qat` portability requirement.

## 5. Non-goals

This lane does not aim to:

1. reopen Gemma 4 work,
2. turn Qwen into a required dependency,
3. replace Orket validators with model-judged truth,
4. claim that one successful tool-call prompt generalizes across unrelated tool families,
5. certify broad prompt quality outside tool-use conformance.

## 6. Workstream Order

## Workstream 0 - Runtime inventory and lane bootstrap

### Goal

Make the lane executable on real local runtimes without hidden model-name drift.

### Tasks

1. Freeze the admitted model ids and provider names for LM Studio and Ollama.
2. Add a runtime inventory preflight that records:
   - installed models,
   - loaded models,
   - resolved runtime target,
   - exact blocker when the requested model is not available.
3. Freeze the first tool-use proof slice and the canonical challenge or harness path used to evaluate it.
4. Record exact judge quant guidance for `FunctionGemma`.

### Exit criteria

1. The lane has one canonical runtime inventory command.
2. The lane can truthfully report whether the requested Gemma target is actually available.
3. No hidden model alias assumptions remain in the live plan.

### Workstream 0 freeze for the current bootstrap slice

The current bootstrap freeze for Workstream 0 is:

1. Canonical runtime inventory command:
   - `python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_inventory.py`
2. Canonical runtime inventory output path:
   - `benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json`
3. Frozen proposer inventory targets:
   - `lmstudio` / `google/gemma-3-12b-it-qat`
   - `lmstudio` / `google/gemma-3-4b-it-qat`
   - admitted LM Studio alias candidates for truthful operator resolution:
     - `gemma-3-12b-it-qat`
     - `gemma-3-4b-it-qat`
4. Frozen judge inventory targets:
   - primary: `ollama` / `functiongemma`
   - admitted Ollama alias candidate for truthful operator resolution:
     - `functiongemma:latest`
   - fallback: `lmstudio` / `google/functiongemma-270m`
   - admitted LM Studio fallback alias candidate:
     - `functiongemma-270m-it`
5. Frozen judge quant guidance:
   - primary judge quant: `Q8_0`
   - smaller quants such as `Q4_0` remain degradation checks only
6. Frozen bootstrap proof slice and harness path:
   - epic authority: `model/core/epics/challenge_workflow_runtime.json`
   - harness script: `scripts/benchmarks/run_local_model_coding_challenge.py`
   - harness output: `benchmarks/staging/General/local_model_coding_challenge_report.json`

This freeze is intentionally narrow.
It binds the first executable bootstrap slice to the existing `challenge_workflow_runtime` harness so the lane can inventory and exercise the admitted Gemma surfaces truthfully.
It does not claim that Workstream 1 has completed the dedicated deterministic tool-use corpus freeze.

## Workstream 1 - Tool-use prompt corpus and acceptance slices

### Goal

Define the fixed prompt-reforge workload before tuning the models.

### Tasks

1. Freeze one bounded tool-use prompt corpus.
2. Freeze one bounded accepted tool-call contract family.
3. Define the measured outputs for each run:
   - accepted tool calls,
   - rejected tool calls,
   - argument-shape defects,
   - turns to first valid tool call,
   - turns to first valid completion,
   - final disposition.
4. Define the precondition and postcondition record for each exercised slice.

### Exit criteria

1. The lane has one deterministic evaluation corpus.
2. The lane reports the same metrics on every rerun.

### Workstream 1 freeze for the current bootstrap slice

The current bootstrap freeze for Workstream 1 is:

1. Canonical bounded corpus:
   - `docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json`
2. Canonical advisory judge protocol:
   - `docs/projects/PromptReforgerToolCompatibility/FUNCTIONGEMMA_TOOL_CALL_JUDGE_PROTOCOL.md`
3. Canonical corpus scoring command:
   - `python scripts/prompt_lab/score_prompt_reforger_gemma_tool_use_corpus.py --run-summary <run_summary> --observability-root <observability_root>`
4. Canonical corpus scoring output path:
   - `benchmarks/staging/General/prompt_reforger_gemma_tool_use_score.json`
5. Frozen bootstrap slices:
   - `PRGTU-CWR01-CODER-SINGLE-WRITE`
   - `PRGTU-CWR01-GUARD-READ-ACCEPT`
   - `PRGTU-CWR03-CODER-MULTI-WRITE`
   - `PRGTU-CWR03-GUARD-MULTI-READ`
   - `PRGTU-CWR04-CODER-PACKAGE-REPAIR`

This freeze remains bounded to the `challenge_workflow_runtime` bootstrap harness.
It does not claim that the broader Prompt Reforger lane is complete or that the bootstrap corpus generalizes beyond the admitted challenge-workflow tool family.

## Workstream 2 - FunctionGemma judge integration

### Goal

Use `FunctionGemma` as the first fast tool-call conformance canary.

### Tasks

1. Add local-provider profile support and harness wiring for `FunctionGemma`.
2. Add a fixed judge protocol that evaluates:
   - tool selection,
   - argument presence,
   - argument shape,
   - extra undeclared tool calls,
   - malformed output shape.
3. Record the exact prompt and exact tool-call output used in every judge decision.
4. Keep Orket parser and validator authority unchanged.

### Exit criteria

1. `FunctionGemma` can score the fixed tool-use slice end-to-end.
2. Judge outputs are recorded as evidence, not authority.

### Workstream 2 freeze for the current bootstrap slice

1. Canonical advisory judge command:
   - `python scripts/prompt_lab/run_functiongemma_tool_call_judge.py --score-report <score_report> --inventory benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json`
2. Canonical advisory judge output path:
   - `benchmarks/staging/General/prompt_reforger_gemma_tool_use_judge.json`
3. Current truthful checkpoint:
   - primary Ollama `functiongemma:latest` is inventory-visible but still all-inconclusive on this machine
   - fallback LM Studio `functiongemma-270m-it` is live and now emits usable advisory tool-call verdicts through the admitted `emit_judgment` tool contract

## Workstream 3 - Gemma proposer and reforge loop

### Goal

Run Prompt Reforger against Gemma-family targets with the judge in the loop.

### Tasks

1. Add the active Gemma-family target selection path:
   - `gemma-3-12b-it-qat` when available,
   - `gemma-3-4b-it-qat` as the portability path.
2. Implement the bounded prompt-rewrite loop for tool-use prompts.
3. Evaluate each rewritten prompt on the fixed tool-use slice.
4. Compare baseline vs candidate prompts using measured tool-call outcomes only.

### Exit criteria

1. The lane can produce baseline and adapted prompt runs for at least one Gemma-family target.
2. Candidate selection is measured, not hand-waved.

## Workstream 4 - Portability proof

### Goal

Prove that the lane remains usable for smaller local hardware.

### Tasks

1. Exercise the portability path on `gemma-3-4b-it-qat`.
2. Record the exact quant and provider setup used for the run.
3. Compare the portability result to the quality-oriented target result when both are available.
4. Truthfully record when the 12B target is blocked while the 4B target remains usable.

### Exit criteria

1. The lane has one truthful smaller-hardware proof path.
2. The lane does not require 12B success to remain executable.

## Workstream 5 - Promotion decision for the first live slice

### Goal

Decide whether the all-Gemma tool-use lane is stable enough to keep as the primary Prompt Reforger execution path.

### Tasks

1. Evaluate whether Gemma-family-only operation is strong enough without Qwen baseline support.
2. Record whether a cross-family baseline is still needed to avoid overfitting.
3. Either:
   - keep all-Gemma as the canonical execution path,
   - add Qwen as a non-authoritative comparison lane,
   - or pause the lane with explicit blockers.

### Exit criteria

1. One explicit recorded decision exists.
2. The lane does not silently drift into a mixed-model architecture.

## 7. Live Proof Rules

Every claimed live slice in this lane must record:

1. model id,
2. provider,
3. quant when relevant,
4. preconditions,
5. postconditions,
6. turn count,
7. accepted tool calls,
8. rejected tool calls,
9. observed path:
   - `primary`
   - `fallback`
   - `degraded`
   - `blocked`
10. observed result:
   - `success`
   - `failure`
   - `partial success`
   - `environment blocker`
11. exact blocker when live proof cannot run.

Structural tests alone are not live proof for this lane.

## 8. First Executable Commands

The lane starts with these concrete operator actions:

1. Confirm local runtime inventory for the admitted model ids.
   - `python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_inventory.py`
2. Confirm `FunctionGemma` judge availability and chosen quant.
   - `python scripts/prompt_lab/run_functiongemma_tool_call_judge.py --score-report <score_report> --inventory benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json`
3. Score the fixed bootstrap corpus against one exercised run.
   - `python scripts/prompt_lab/score_prompt_reforger_gemma_tool_use_corpus.py --run-summary <run_summary> --observability-root <observability_root>`
4. Run one bounded reforge cycle and compare measured tool-call outcomes.
   - `python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_cycle.py --targets both --runs 1`

The canonical bootstrap commands are now frozen in Workstreams 0-5 at the inventory, scorer, judge, and cycle surfaces above.

## 9. Paused Checkpoint Reopen Criteria

The lane is paused until one bounded change set can truthfully clear the remaining portability blocker:

1. Portability blocker:
   - `gemma-3-4b-it-qat` must clear the frozen corpus on `python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_cycle.py --targets both --runs 1` with the canonical output `benchmarks/staging/General/prompt_reforger_gemma_tool_use_cycle.json`
2. Same-change proof requirement:
   - any reopen must rerun the canonical inventory, cycle, and judge artifacts and update roadmap and authority docs with the observed result

## 10. Planned Outputs

This lane is expected to produce:

1. one live Prompt Reforger tool-use execution path,
2. one fixed tool-use evaluation corpus,
3. one `FunctionGemma`-based judge path,
4. one portability proof path,
5. one explicit decision about whether all-Gemma remains the canonical execution strategy.
