# Prompt Lab

This directory is optional and never runtime-critical.

## Eval Harness
Run:

```bash
python scripts/prompt_lab/eval_harness.py
```

Outputs:
- `benchmarks/results/prompt_eval_metrics.json`

Tracked metrics:
- `tool_parse_rate`
- `required_action_completion_rate`
- `status_progression_rate`
- `guard_decision_reach_rate`

## PromptWizard
PromptWizard is not required for runtime.
If introduced later, keep it isolated under this directory and behind explicit scripts.

## Offline Optimize
Generate candidate prompt versions without mutating `model/core/*`:

```bash
python scripts/prompt_lab/optimize_prompts.py --root . --out prompts/candidates --kind all --source-status stable --bump patch
```

Outputs:
- `prompts/candidates/manifest.json`
- `prompts/candidates/role/*.candidate.json`
- `prompts/candidates/dialect/*.candidate.json`

## Candidate Comparison
Compare candidate run outputs against stable baselines:

```bash
python scripts/prompt_lab/compare_candidates.py \
  --stable-eval benchmarks/results/prompt_eval_metrics.stable.json \
  --candidate-eval benchmarks/results/prompt_eval_metrics.candidate.json \
  --stable-patterns benchmarks/results/live_patterns.stable.json \
  --candidate-patterns benchmarks/results/live_patterns.candidate.json \
  --thresholds benchmarks/results/prompt_promotion_thresholds.json
```

Exit code:
- `0` when candidate is non-regressive by configured gates.
- `1` when regression is detected.
