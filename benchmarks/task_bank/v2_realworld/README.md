# Real-World Task Bank (v2)

This task bank is designed to test concrete coding behavior, not template compliance.

Each task includes:
- `problem`: plain-language requirement
- `function_signature`: required function name/signature
- `constraints`: behavioral constraints
- `io_examples`: human-readable examples
- `evaluation`: executable examples used by the runner

## Run a Single Task

```powershell
python scripts/live_card_benchmark_runner.py --task benchmarks/task_bank/v2_realworld/tasks.json
```

Use a single-task JSON object path for `--task`. Example:

```powershell
python -c "import json,pathlib; t=json.loads(pathlib.Path('benchmarks/task_bank/v2_realworld/tasks.json').read_text())[0]; p=pathlib.Path('workspace/realworld/task001.json'); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(t,indent=2)+'\n'); print(p)"
python scripts/live_card_benchmark_runner.py --task workspace/realworld/task001.json --run-dir workspace/realworld/task001_run
```

## Run a Batch (Card Path)

```powershell
python scripts/run_determinism_harness.py ^
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json ^
  --runs 1 ^
  --venue local-hardware ^
  --flow live-card ^
  --runner-template "python scripts/live_card_benchmark_runner.py --task {task_file} --venue {venue} --flow {flow} --run-dir {run_dir}" ^
  --artifact-glob live_runner_output.log ^
  --task-id-min 1 ^
  --task-id-max 20 ^
  --output benchmarks/results/live_card_v2_realworld_001_020_determinism.json
```

## Run a Batch (Rock Path, One Command)

```powershell
python scripts/run_live_rock_benchmark_suite.py ^
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json ^
  --runs 1 ^
  --task-id-min 1 ^
  --task-id-max 20 ^
  --raw-out benchmarks/results/live_rock_v2_001_020_determinism_report.json ^
  --scored-out benchmarks/results/live_rock_v2_001_020_scored_report.json
```

## Harder Phase (Tasks 021-040)

```powershell
python scripts/run_live_rock_benchmark_suite.py ^
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json ^
  --runs 1 ^
  --task-id-min 21 ^
  --task-id-max 40 ^
  --raw-out benchmarks/results/live_rock_v2_021_040_determinism_report.json ^
  --scored-out benchmarks/results/live_rock_v2_021_040_scored_report.json
```

## Advanced Phase (Tasks 041-060)

```powershell
python scripts/run_live_rock_benchmark_suite.py ^
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json ^
  --runs 1 ^
  --task-id-min 41 ^
  --task-id-max 60 ^
  --raw-out benchmarks/results/live_rock_v2_041_060_determinism_report.json ^
  --scored-out benchmarks/results/live_rock_v2_041_060_scored_report.json
```

## Expert Phase (Tasks 061-080)

```powershell
python scripts/run_live_rock_benchmark_suite.py ^
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json ^
  --runs 1 ^
  --task-id-min 61 ^
  --task-id-max 80 ^
  --raw-out benchmarks/results/live_rock_v2_061_080_determinism_report.json ^
  --scored-out benchmarks/results/live_rock_v2_061_080_scored_report.json
```
