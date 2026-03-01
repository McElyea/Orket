# Benchmark Failure Ledger

Last updated: 2026-02-18 (UTC)
Owner: Benchmark reliability loop
Scope: v2 real-world live rock benchmarks (`001-080`)

## Purpose
This document records benchmark failures, root causes, and remediations so weak spots are explicit and traceable.

## Incident Log
| Date | Area | Symptom | Root Cause | Remediation | Commit |
|---|---|---|---|---|---|
| 2026-02-18 | Rock runtime | `name 'Path' is not defined` during rock flow | Missing `Path` import in bug-fix phase service | Import fix in `orket/domain/bug_fix_phase.py` | `79be747` |
| 2026-02-18 | Rock runner | False validation failures (`missing agent_output/main.py`) with nested rock workspaces | Runner validated wrong directory level | Added effective nested run-dir resolution in rock runner | `79be747` |
| 2026-02-18 | Prompting | Frequent weak function outputs (boilerplate, formatting drift) | Insufficient explicit output contract | Tightened function-mode prompt contract + exact-output guidance | `3d5a6af` |
| 2026-02-18 | Quality checker | Valid logic falsely marked trivial | AST statement counter undercounted nested logic | Fixed non-trivial function-body counting in quality checks | `3d5a6af` |
| 2026-02-18 | Reconciler noise | `reconciler_rock_parse_failed`, `discovery_reconcile_failed`, `reconciler_epic_parse_failed` spam | Path resolution bug in reconciler file access | Reconciler switched to direct stable `Path` reads/writes | `7d299bc` |
| 2026-02-18 | Sandbox noise | `sandbox_deploy_failed` during function benchmarks | Sandbox deploy attempted for non-web benchmark outputs | Benchmark runners now set `ORKET_DISABLE_SANDBOX=1` | `7d299bc` |
| 2026-02-18 | Scoring | Hidden run failures not always reflected as failing tasks | Pass logic allowed low-band success with non-zero exits | Scoring pass now requires `success_rate == 1.0` | `23df7dc` |

## Task-Level Corrections
### Refined (same task retained)
- `022`: clarified pair selection to lexicographically earliest (`i`, then `j`) to remove ambiguous two-sum outputs.
- `030`: clarified signed-token parsing for RPN; fixed malformed evaluation arg shape.
- `034`: clarified LRU get/put semantics to prevent invalid cache mutation patterns.
- `046`: enforced deterministic topo-order tie-break (smallest available node first).

### Replaced (unstable/ambiguous tasks swapped)
- `059`: replaced multiple times; final stable task is `find_duplicate_number(values)`.
- `060`: replaced; final stable task is `asteroid_collision(values)`.
- `064`: replaced with `longest_consecutive_length(values)`.
- `065`: replaced with `gas_station_start(gas, cost)`.
- `068`: replaced with `validate_stack_sequences(pushed, popped)`.
- `070`: replaced with `can_attend_all_meetings(intervals)`.
- `072`: replaced with `min_path_sum(grid)`.
- `077`: replaced with `max_container_area(heights)` after repeated instability.
- `079`: replaced with `max_product_subarray(values)`.
- `080`: replaced with `find_duplicate_number(values)`.

## Current Reliability Snapshot
- Live rock `001-080`: deterministic `80/80`, failing tasks `0`, overall score `5.0`.
- Reports:
  - `benchmarks/results/live_rock_v2_001_080_determinism_report.json`
  - `benchmarks/results/live_rock_v2_001_080_scored_report.json`

## Follow-up Policy
For every future benchmark update:
1. Log every first-fail task with failure reason and run id.
2. Classify fix as `prompt`, `checker`, `task-spec`, `runtime`, or `replacement`.
3. Record commit hash and rerun evidence before closing.
