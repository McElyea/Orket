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
