# Core 0.7.5 source checkpoint

Recorded: 2026-10-04 (America/Denver)

## What changed

This patch addresses demonstrated workflow and benchmark limitations after the
0.7.4 comparison. It adds two prepared stored workflows with declared acceptance,
conservative preflight, isolated benchmark projects with real function oracles,
outcome-aware service load, idle streaming diagnostics and retained Git fixtures.
It fixes background API ownership, missing-target admission, service port handling,
typed streaming failures and whole-file review pattern scanning. The recovered
historical fixture exposed that scanner's false-green behavior; fresh files-mode
reviews now report retained TODO/FIXME text with path and line attribution.

Start with [prepared workflow recipes](../../../examples/stored_workflows/README.md).
The [readiness contract](../../specs/WORKFLOW_BENCHMARK_READINESS.md) and
[contract delta](../../architecture/CONTRACT_DELTA_WORKFLOW_WINS_2026-10-04.md)
define the bounded behavior and migration. API clients must handle missing-target
HTTP 404; benchmark callers must provide supported explicit evaluation cases.

- `compatibility_status`: `breaking`
- `affected_audience`: `operator_only`
- `migration_requirement`: `required`

Core advances from 0.7.4 to 0.7.5 with a matching annotated source tag. Runtime
behavior changes in this checkpoint; SDK sources, the exact SDK dependency pin
and other dependency selections do not. The accepted published installed pair
remains core/SDK 0.7.2. This source tag does not claim a new wheel installation or
SDK pairing, and no empty distribution release is needed.

## What was verified

The [staging report](../../../benchmarks/staging/General/workflow_limitation_repairs.md)
and its adjacent JSON retain exact outcomes, timings, inputs, failed attempts,
receipt hashes and proof boundaries. Runtime proof used the Windows editable
candidate environment with core metadata 0.7.4 and SDK 0.7.2; the final 0.7.5 bump
only changes version metadata. All inference kept llama.cpp and the selected
`orcarouter_qwen3.8-27b-uncensored-q4_k_l` model. Sandbox creation was disabled.

- **Live model:** two final prepared standard runs accepted all three cards;
  final CLI QA and TCP API QA each accepted both cards. One card benchmark and
  two consecutive collection benchmarks accepted task 008's function examples.
- **Live TCP:** each of three baseline load executions observed 1,040 samples with
  zero failures, including 40 expected missing-target refusals. These refusal
  controls are separate from the actual accepted API QA job.
- **Live, bounded streaming:** ten full loops and 60 scenario verdicts passed;
  s7/s9 observed real model deltas. Three idle-server diagnostics passed. These
  runs do not establish the cause of the prior endurance failure.
- **Native deterministic:** exact historical 30-page commits and policy were
  recovered without modifying the original fixture. All 1,000 repetitions
  produced the expected `changes_requested` decision and one localized finding.
  No model calls were made by this review benchmark.
- **Native controlled and structural regression proof:** 281 targeted tests
  passed (zero failures/skips, one existing Starlette deprecation warning).
  Tests exercise actual local filesystems, SQLite, Git and HTTP boundaries plus
  controlled contract cases. They cover background failure/cancellation ownership,
  verifier refusal, missing-target admission and timeout error identity; they are
  not a substitute for the separate real model/TCP evidence. Changed-Python Ruff
  passed, including the seven previously reported findings in touched scripts.
- **Structural governance:** docs/project hygiene, generated/current authority,
  dependency direction, staging index and core release policy checks passed.
  Authority validation explicitly reports `current_proof_established: false`;
  runtime claims come from the separate live evidence above. The first dependency
  check caught a new interface-to-legacy-exception edge; moving target observation
  into the application service cleared it. The final API QA/load and 281-test
  selection were rerun after that correction, with original failures retained.
- **Structural inventory:** 26 nonempty stored epics, two ready and 24 blocked;
  six empty placeholders. The v2 bank contains 70 supported function definitions
  out of 80 tasks; v1's 100 metadata-only tasks remain unsupported.

All retained task command receipts confirm Windows Job cleanup and complete
capture. Task service ports were released. Final preservation and publication
receipts live under `.tmp/workflow-wins/closeout/`; raw run receipts remain under
`.tmp/workflow-wins/`, and reusable isolated evidence under
`C:/Source/Orket-wins075/`. Ignored raw evidence is local, not a public asset.
Benchmark evidence stays in staging; this commit does not approve promotion.

## What was not verified

No full suite or 89% coverage campaign, hosted CI, new wheel installation, new SDK
pairing, non-Windows execution, alternate model/provider, 1,000-loop live streaming,
real cold model reload or thermal endurance claim is added. Only v2 task 008 was
run live here. Timings are host observations with some overlapping CPU/load work;
they do not establish a statistically controlled speedup or cross-model ranking.
The controlled timeout test establishes error attribution, not the cause of the
historical model stall. API existence checks are observations, not reservations.

## Remaining blockers or drift

The other 24 nonempty epics need task-specific inputs, executable roles or
acceptance; six assets remain placeholders. Undefined task-bank shapes need real
oracles before admission. Accepted model runs still contain repaired/nonconformant
truth packets (`silent_repaired_success`), and uncontrolled benchmark quality
remains `POLLUTED`. Declared acceptance does not prove general correctness. The
prior loop-6 streaming failure is retained and its root cause remains unresolved.

The architecture checklist is scoped to this change: AC-01 through AC-06 pass
for allowed imports, explicit bounded review inputs and application-owned API
effects; AC-07 is partial because the existing truth-packet warning remains in
`orket/runtime/summary/run_summary.py` and accepted-run projections. This
patch reports it without widening or concealing it; remediation remains owned
by Orket Core under the active architectural-truth umbrella and
`docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`. AC-08 through AC-10 pass for documented additive error
identity, retained replay inputs and same-change contract/authority updates.
The already oversized `tests/interfaces/test_api.py` grows by one line to make
the existing test fixture honor real target resolution and nonblocking task
registration. `orket/streaming/model_provider.py` grows by one line to retain
the error class alongside its message, including empty-message timeouts. Other
oversized touched Python files shrink. These bounded correctness exceptions
avoid a duplicate API fixture or a separate streaming error authority.

PRR stays complete with no executable PRR work. PRR-S1 and broader architectural
debt remain deferred under the active umbrella; whole-umbrella retirement remains
out of scope. The October 6, 2026 00:00 America/Denver cutoff and final six-hour
verification/publication reserve remain unchanged. The operator board override,
selected provider/server, other worktrees and published releases are preserved.

## Exact files touched

Repository-wide source, contract, evidence and release changes (40 files):

- `CHANGELOG.md`
- `CURRENT_AUTHORITY.md`
- `benchmarks/job_outcomes.py`
- `benchmarks/phase5_load_test.py`
- `benchmarks/staging/General/workflow_limitation_repairs.json`
- `benchmarks/staging/General/workflow_limitation_repairs.md`
- `benchmarks/staging/README.md`
- `benchmarks/staging/index.json`
- `docs/README.md`
- `docs/architecture/CONTRACT_DELTA_WORKFLOW_WINS_2026-10-04.md`
- `docs/architecture/current_authority.json`
- `docs/releases/0.7.5/PROOF_REPORT.md`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `docs/specs/MODEL_STREAM_LIFETIME.md`
- `docs/specs/REVIEW_RUN_V0.md`
- `docs/specs/WORKFLOW_BENCHMARK_READINESS.md`
- `examples/stored_workflows/README.md`
- `examples/stored_workflows/prepare.py`
- `model/core/epics/qa_completion_test.json`
- `model/core/epics/standard.json`
- `orket/application/review/lanes/deterministic.py`
- `orket/application/services/api_background_invocation_service.py`
- `orket/interfaces/api_invocation.py`
- `orket/interfaces/routers/system.py`
- `orket/streaming/model_provider.py`
- `pyproject.toml`
- `scripts/README.md`
- `scripts/benchmarks/function_acceptance.py`
- `scripts/benchmarks/isolated_project.py`
- `scripts/benchmarks/live_card_benchmark_runner.py`
- `scripts/benchmarks/live_rock_benchmark_runner.py`
- `scripts/governance/check_workflow_preflight.py`
- `scripts/reviewrun/run_30page_consistency.py`
- `scripts/streaming/diagnose_llama_stream.py`
- `scripts/streaming/real_service_stress.py`
- `scripts/streaming/run_live_1000_consistency.py`
- `scripts/streaming/run_stream_scenario.py`
- `tests/integration/test_review_files_patterns.py`
- `tests/integration/test_workflow_wins.py`
- `tests/interfaces/test_api.py`

Ignored task receipts and helpers live under `.tmp/workflow-wins/` and `.tmp/wins_*.py`; isolated projects are retained at `C:/Source/Orket-wins075/`. The development environment is `C:/Users/jonmc/AppData/Local/Temp/orket-prr-v1/wins075/`. These are local verification artifacts, not staged source files.
