# Stored workflow runtime comparison

Date: 2026-10-04. Windows only. Candidate evidence; not published.

All 16 nonempty stored epics were run once in isolated projects using the installed Orket/SDK 0.7.2 pair and the existing llama.cpp `orcarouter_qwen3.8-27b-uncensored-q4_k_l` server. None completed. The remaining 16 epic files contain no cards. Original workflow bytes were preserved.

Times below are engine-reported **time to failure**, not successful completion or model-speed measurements. Native command wall times, startup overhead and exact argv are retained separately in the process receipts.

| Stored epic | Cards | Seconds to failure | Blocker |
| --- | ---: | ---: | --- |
| auth_manager | 3 | 0.051 | missing_reviewer_seat |
| benchmark_live_008_7b53edf8 | 1 | 13.304 | missing_completion_acceptance |
| branding | 2 | 0.048 | missing_reviewer_seat |
| challenge_workflow_runtime | 12 | 25.060 | missing_completion_acceptance |
| core_baseline | 3 | 0.051 | missing_reviewer_seat |
| idea_brainstorming_session | 3 | 0.048 | missing_reviewer_seat |
| model_reforge | 3 | 84.089 | missing_completion_acceptance |
| price_arbitrage_system | 9 | 32.892 | unavailable_tool |
| qa_completion_test | 2 | 39.748 | missing_completion_acceptance |
| requirements_refinement | 3 | 0.051 | missing_reviewer_seat |
| requirements_team | 3 | 0.054 | missing_reviewer_seat |
| role_matrix_soak | 24 | 55.961 | missing_completion_acceptance |
| standard | 3 | 35.441 | missing_completion_acceptance |
| system_optimization_q1 | 2 | 0.053 | missing_reviewer_seat |
| ui_update | 2 | 0.056 | missing_reviewer_seat |
| web_dev | 2 | 0.050 | missing_reviewer_seat |

Nine teams lack the required reviewer seat; six epics reached the missing-acceptance gate; the price-arbitrage workflow requested unavailable `google_web_search`. All 16 lack explicit completion acceptance, including those that failed earlier. These are stored-asset blockers; no acceptance rule was relaxed.

## Benchmark suites

| Suite | Executions | Mean seconds | Meaning |
| --- | ---: | ---: | --- |
| phase4-raw | 60 | 0.062 | Native fixture/control only; no model work |
| phase5-raw | 40 | 0.062 | Native fixture/control only; no model work |
| v1-control | 200 | 0.052 | Native fixture/control only; no model work |
| v2_realworld-control | 160 | 0.056 | Native fixture/control only; no model work |
| card-raw | 1 | 13.768 | Failed workload probe; wrapper exited zero |
| rock-raw | 1 | 1.879 | Failed workload probe; wrapper exited zero |

The 60 Phase 4 and 40 Phase 5 fixture executions succeeded, as did two control repetitions for each of the 100 v1 and 80 v2 tasks. This is **460 native fixture/control executions**, not 460 solved coding tasks. The Phase 4/5 runner synthesizes its pass fields from task metadata. Control repeatability establishes only harness behavior.

The v1 card-suite probe failed completion acceptance. The subsequent v2 collection-suite probe failed on a dangling board reference to the prior temporary epic after its runner deleted that epic. Both suite commands exited zero because report generation succeeded; their task rows correctly retain exit 2 and failing scores.

Fresh standalone v2 probes reached the actual provider after the interpreter fix: task 001 failed tool-call recovery after 23.794 engine seconds; task 008 reached the acceptance gate after 14.885 seconds. The generated factorial passed its three example checks, but its card/epic did not acquire completion acceptance.

The full 100/80 model suites were not expanded after these concrete blockers. The 13 stored quant/model matrices target older model IDs and quantizations; their model/provider/context sweeps were not run or silently substituted. Only the selected model was used. No credits were purchased.

## Historical comparison and limits

- Gemma 4 26B A4B via LM Studio: three historical coding-challenge failures in 63.582, 64.606 and 63.520 seconds (mean 63.903), reaching CWR-04. The new Qwen run stopped at CWR-01 in 25.060 seconds. Different failure stages and runtime contracts prevent a speedup claim.
- Historical v2 80-task aggregate: 4.532 seconds/task; historical v1 100-task aggregate: 7.469 seconds/task. These are retained older reports, not new proof or a matched model comparison. Aggregate model identity and correctness equivalence were not established. Single-run legacy determinism labels are not repeatability proof.
- Historical Phase 4/5 means were 0.078/0.072 seconds. Their fixture nature makes them unsuitable for model comparisons.
- The earlier seeded four-card bug-fix example completed in 213.175 seconds on the current model, with eight passing tests and nine fixed cases. That prior live evidence is reused; this task did not rerun it. Its temperature/task/prompt inputs differ from these older templates.

## Changes and verification

Repository-owned benchmark Python children now use `sys.executable`. The harness uses native Windows argv parsing, fixing quoted interpreter paths and preserving literal arguments. Native regression controls exercise real child processes and CLI example evaluation. 37 targeted tests passed. Successful post-fix suite launches are live Windows proof of the repaired launch paths; failed model outcomes remain failed.

Scoped lint is clean except two pre-existing `SIM105` findings in the collection runner, confirmed against HEAD. Stored workflow migration, broad architectural debt, cross-platform behavior, old-model reruns, statistical performance and full product correctness remain unverified. No release was made; changes are uncommitted.

## Evidence and preservation

Exact commands, failed attempts, logs and native ownership receipts: `.tmp/workflow-comparison/` in the checkout (`probes-01`, `probes-02`, `suites-01`, `suites-02`). Isolated projects: `C:\Source\Orket-workflow-comparison`. The sibling JSON records original asset hashes, per-run summary hashes, historical references and final preservation observations. Earlier interpreter and quoted-path failures were retained.

Task-owned commands settled and cleanup was confirmed. The operator board, its skip-worktree flag, selected model/template, operator server PID/start time and other worktrees were preserved. Existing bug-fix example files and accepted PRR evidence were not edited.

## Exact repository files touched

- `scripts/README.md`
- `scripts/benchmarks/determinism_cli.py`
- `scripts/benchmarks/live_card_benchmark_runner.py`
- `scripts/benchmarks/live_rock_benchmark_runner.py`
- `scripts/benchmarks/run_determinism_harness.py`
- `scripts/benchmarks/run_live_card_benchmark_suite.py`
- `scripts/benchmarks/run_live_rock_benchmark_suite.py`
- `tests/scripts/test_benchmark_windows_command.py`
- `benchmarks/staging/General/stored_workflow_runtime_comparison.json`
- `benchmarks/staging/General/stored_workflow_runtime_comparison.md`
- `benchmarks/staging/index.json`
- `benchmarks/staging/README.md`

Ignored helper/evidence files and external project inventories are listed in `.tmp/workflow-comparison/file_inventory.json`.
