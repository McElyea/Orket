# Core 0.7.6 source checkpoint

Recorded: 2026-10-04 (America/Denver)

## What changed

This patch adds real CLI-example acceptance to the existing benchmark adapter,
corrects task-bank newline expectations, makes prepared configuration effective,
and adds a bounded sanity recipe. It fixes a quote-sensitive Python main-guard
check and discloses retained runtime repair/nonconformance warnings in operator
history/detail. Fresh-build contributor guidance addresses demonstrated wheel
contamination from a reused cache. No acceptance rule is weakened to hide model
failures.

Use the [prepared workflow recipes](../../../examples/stored_workflows/README.md)
and [readiness contract](../../specs/WORKFLOW_BENCHMARK_READINESS.md).
CLI consumers use revision 2 task identities and the private
`scripts.benchmarks.task_acceptance` adapter. Operator clients can display the
additive `runtime_truth` fields without changing completion logic. The
[contract delta](../../architecture/CONTRACT_DELTA_WORKFLOW_FOLLOWUP_2026-10-04.md)
records migration and authority boundaries.

- `compatibility_status`: `breaking`
- `affected_audience`: `operator_only`
- `migration_requirement`: `required`

Core advances from 0.7.5 to 0.7.6 with an annotated source tag. SDK source and its
0.7.2 dependency pin remain unchanged. This checkpoint includes a **local installed
candidate smoke**, not a new public distribution or full SDK pairing campaign.
The accepted published core/SDK pair remains 0.7.2; its releases are preserved.

## What was verified

The [staging report](../../../benchmarks/staging/General/workflow_followup_repairs.md)
and adjacent JSON retain exact outcomes, timings, input identities and failures.
All real inference used Windows and the existing selected llama.cpp model
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`, with routine sandbox creation disabled.

- **Live model:** original matrix 11/15 passed; ten CLI and five function tasks
  were exercised. Task 019 then passed a separate fresh run after fixing its
  source-quality checker. Original matrix failures remain unchanged.
- **Live installed CLI:** a fresh core 0.7.6 wheel plus the verified public SDK
  0.7.2 wheel passed dependency/origin checks, SDK version and the prepared sanity
  workflow with one durable accepted completion. The first contaminated build
  and its import failure remain retained. Package changes match wheel bytes.
- **Live installed API:** two real QA attempts failed the hallucination-scope
  guard; actual TCP views disclosed repair and unaccepted completion. This proves
  the negative view path, not accepted QA completion. Native service load and
  port cleanup have separate receipts.
- **Live bounded streaming:** all 100 loops and 600 scenario verdicts passed in
  830.368 seconds. Real s7/s9 cases observed deltas; controlled refusal/cancellation
  cases remain separate. No cold reload or 1,000-loop acceptance is implied.
- **Native controlled and structural:** 222 targeted tests and changed-Python
  Ruff passed. Native file/SQLite/process acceptance and configuration checks are
  separate from controlled warning-projection and syntax checks. Zero test skips
  or failures; one existing Starlette deprecation warning.
- **Structural inventory:** three of 26 nonempty epics ready, 23 blocked and six
  empty assets. All 80 v2 definitions now admit structurally; v1 remains 0/100.
- **Structural governance:** docs/project hygiene, generated/current authority,
  dependency direction, staging index, core policy and whitespace checks passed.
  Authority validation explicitly leaves `current_proof_established: false`;
  runtime proof is the separate live evidence above.

Task receipts retain native Windows ownership and source fingerprints. Evidence
roots are `.tmp/workflow-followup/` and `C:/Source/Orket-followup076/`; these raw
files are local and ignored. The staging report does not approve benchmark
publication. Prior 0.7.5 deterministic review results are historical, reused only
for unchanged review inputs. Timing controls remain incomplete (`POLLUTED`).

Final cleanup inspection found no surviving task-owned command processes and
confirmed service ports 18082/18083 released. The same operator server PID/start
time, idle slot, model/template, skip-worktree board bytes and other worktree heads
were preserved. The 1,246-file candidate package source still matches its retained
wheel-build manifest. Ignored closeout receipts retain those checks and hashes.

## What was not verified

No full suite or 89% coverage campaign, hosted CI, non-Windows execution,
alternate provider/model, full task-bank model run, cold reload, public wheel
publication, full SDK pairing matrix or 1,000-loop streaming acceptance is added.
Accepted nonconformant run-view warning behavior has contract proof; live API
proof here is the failed QA path. The installed sanity receipt is deliberately
narrow and does not establish general system health. No speedup is inferred.

## Remaining blockers or drift

Tasks 025, 040 and 060 have real generated-output failures. Both installed API QA
attempts fail the hallucination-scope guard after corrective reprompt. Twenty-three
stored epics still lack sufficient executable semantics; six assets are empty.
Historical repaired/nonconformant truth packets remain unchanged: this patch
discloses them, rather than repairing the underlying producer. The earlier loop-6
streaming failure's cause remains unresolved.

Architecture checklist: AC-01 through AC-06 pass for this scope's existing
dependency flow and application-owned projections. AC-07 improves user-visible
truth but remains partial because the historical packet producer issue is not
fixed. AC-08 through AC-10 pass for additive documented fields, retained replay
inputs and same-change authority updates. No touched oversized Python file grows.

PRR stays complete with no executable PRR work. PRR-S1 and broader architectural
debt remain deferred, and the architectural-truth umbrella remains active.
Whole-umbrella retirement is outside scope. The October 6, 2026 00:00
America/Denver cutoff and final six-hour verification/publication reserve remain.
The operator board override, selected provider/server, other worktrees and
published releases are preserved. Exact live failures above are resumable from
their retained source/command receipts; no provider switch or paid billing is
needed or authorized by this checkpoint.

## Exact files touched

Repository-wide source, contracts, evidence and release metadata (33 paths):

- `CHANGELOG.md`
- `CURRENT_AUTHORITY.md`
- `benchmarks/staging/General/workflow_followup_repairs.json`
- `benchmarks/staging/General/workflow_followup_repairs.md`
- `benchmarks/staging/README.md`
- `benchmarks/staging/index.json`
- `benchmarks/task_bank/v2_realworld/tasks.json`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/CONTRIBUTOR.md`
- `docs/architecture/CONTRACT_DELTA_WORKFLOW_FOLLOWUP_2026-10-04.md`
- `docs/architecture/current_authority.json`
- `docs/releases/0.7.6/PROOF_REPORT.md`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`
- `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`
- `docs/specs/WORKFLOW_BENCHMARK_READINESS.md`
- `examples/stored_workflows/README.md`
- `examples/stored_workflows/prepare.py`
- `model/core/epics/sanity_test.json`
- `orket/application/services/operator_runtime_service.py`
- `orket/interfaces/operator_view_models.py`
- `pyproject.toml`
- `scripts/README.md`
- `scripts/benchmarks/function_acceptance.py` (removed; adapter moved below)
- `scripts/benchmarks/live_card_benchmark_runner.py`
- `scripts/benchmarks/live_rock_benchmark_runner.py`
- `scripts/benchmarks/source_requirements.py`
- `scripts/benchmarks/task_acceptance.py`
- `tests/contract/test_benchmark_source_requirements.py`
- `tests/integration/test_benchmark_cli_acceptance.py`
- `tests/integration/test_prepared_workflow_policy.py`
- `tests/integration/test_workflow_wins.py`
- `tests/interfaces/test_operator_truth_disclosure.py`

Ignored task-owned helpers/receipts, wheel artifacts and preserved build cache
under `.tmp/workflow-followup/` are local verification material, not committed
source. Isolated projects and candidate environments are retained for reproduction.
