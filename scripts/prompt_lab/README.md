# Prompt Lab

Optional tooling for prompt evaluation and candidate comparison.

This directory is not runtime-critical for core orchestration.

## Eval Harness
```bash
python scripts/prompt_lab/eval_harness.py
```
Output: `benchmarks/results/prompt_eval_metrics.json`

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
python scripts/prompt_lab/compare_candidates.py --stable-eval benchmarks/results/prompt_eval_metrics.stable.json --candidate-eval benchmarks/results/prompt_eval_metrics.candidate.json --stable-patterns benchmarks/results/live_patterns.stable.json --candidate-patterns benchmarks/results/live_patterns.candidate.json --thresholds benchmarks/results/prompt_promotion_thresholds.json
```
Exit code:
1. `0`: candidate passes configured gates.
2. `1`: candidate fails configured gates.
