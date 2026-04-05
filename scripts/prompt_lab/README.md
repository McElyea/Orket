# Prompt Lab

Optional tooling for prompt evaluation and candidate comparison.

This directory is not runtime-critical for core orchestration.

## Eval Harness
```bash
python scripts/prompt_lab/eval_harness.py
```
Output: `benchmarks/results/prompt_lab/prompt_eval_metrics.json`

## Prompt Reforger Gemma Lane Inventory
```bash
python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_inventory.py
```
Output: `benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json`

## Prompt Reforger Gemma Corpus Scoring
```bash
python scripts/prompt_lab/score_prompt_reforger_gemma_tool_use_corpus.py --run-summary <run_summary> --observability-root <observability_root>
```
Output: `benchmarks/staging/General/prompt_reforger_gemma_tool_use_score.json`

## FunctionGemma Tool-Call Judge
```bash
python scripts/prompt_lab/run_functiongemma_tool_call_judge.py --score-report <score_report> --inventory benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json
```
Output: `benchmarks/staging/General/prompt_reforger_gemma_tool_use_judge.json`
Note: the script enables the admitted native `emit_judgment` tool contract for FunctionGemma and will truthfully fall back to the LM Studio judge path when the Ollama path is available but all-inconclusive.

## Prompt Reforger Gemma Cycle
```bash
python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_cycle.py --targets both --runs 1
```
Output: `benchmarks/staging/General/prompt_reforger_gemma_tool_use_cycle.json`

## Prompt Reforger Guide-Model Comparison
```bash
python scripts/prompt_lab/run_prompt_reforger_guide_model_comparison.py --targets portability --runs 1 --guide-spec "qwen7b|ollama|qwen2.5-coder:7b" --guide-spec "gemma12b|lmstudio|google/gemma-3-12b-it-qat"
```
Output: `benchmarks/staging/General/prompt_reforger_guide_model_comparison.json`
Note: this harness keeps the Gemma target lane fixed and compares guide models by generated prompt-candidate quality from the corpus scoreboards rather than by outer challenge pass/fail.

## Candidate Generation
```bash
python scripts/prompt_lab/optimize_prompts.py --root . --out prompts/candidates --kind all --source-status stable --bump patch
```
Outputs:
1. `prompts/candidates/manifest.json`
2. `prompts/candidates/role/*.candidate.json`
3. `prompts/candidates/dialect/*.candidate.json`

## Candidate Comparison
```bash
python scripts/prompt_lab/compare_candidates.py --stable-eval benchmarks/results/prompt_lab/prompt_eval_metrics.stable.json --candidate-eval benchmarks/results/prompt_lab/prompt_eval_metrics.candidate.json --stable-patterns benchmarks/results/prompt_lab/live_patterns.stable.json --candidate-patterns benchmarks/results/prompt_lab/live_patterns.candidate.json --thresholds benchmarks/results/prompt_lab/prompt_promotion_thresholds.json
```
Exit code:
1. `0`: candidate passes configured gates.
2. `1`: candidate fails configured gates.
