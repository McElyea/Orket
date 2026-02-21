# Real-World Task Bank (v2)

`tasks.json` contains coding tasks used by benchmark runners.

## Task Schema (per task)
1. `problem`
2. `constraints`
3. `io_examples`
4. `evaluation`

Mode-specific fields:
1. `function` mode: includes `function_signature` and `evaluation.type=function_examples`.
2. `module` / `service` / `system` modes: use `evaluation.type=cli_examples`.

## Run One Task
```powershell
python scripts/live_card_benchmark_runner.py --task <single-task-json>
```

## Run Task Ranges
Use the suite runner:
```powershell
python scripts/run_live_rock_benchmark_suite.py --task-bank benchmarks/task_bank/v2_realworld/tasks.json --runs 1 --task-id-min <min> --task-id-max <max> --raw-out <raw.json> --scored-out <scored.json>
```

For quant sweep and diagnostics workflows, use `docs/QUANT_SWEEP_RUNBOOK.md`.
