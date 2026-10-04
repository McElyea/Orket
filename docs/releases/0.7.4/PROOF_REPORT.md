# Core 0.7.4 source checkpoint

Recorded: 2026-10-04 (America/Denver)

## What changed

This patch checkpoint commits the complete pending demo and benchmark work on
main under the contributor version/tag rule. It adds the reusable four-card
bug-fix example, fixes Windows benchmark interpreter/argv handling, enters the
API lifespan in the streaming scenario harness, and retains both comparison
reports as staging candidates. The scripts documentation and regression tests
describe and exercise those changes.

The core version advances from 0.7.3 to 0.7.4. Runtime and SDK implementation,
dependencies, provider selection and published package assets are unchanged.
The verified installed target remains core 0.7.2 plus SDK 0.7.2. The matching
annotated Git tag identifies this source checkpoint; it does not establish a
new installed pair or require an empty distribution release.

- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

## What was verified

Accepted earlier evidence is reused for unchanged inputs and its original scope:

- **Live:** the [four-card example](../../../examples/bug_fix/README.md) completed
  on Windows through llama.cpp in 213.175 seconds. All four completion receipts
  were accepted; six regression tests rejected the baseline, eight tests passed
  after repair, and nine declared oracle cases passed. Its repaired/nonconformant
  truth-packet warning remains visible.
- **Live native Windows:** benchmark child launches and literal/quoted argv were
  exercised with actual subprocesses. The prior targeted selection passed 37
  tests. The [stored-workflow comparison](../../../benchmarks/staging/General/stored_workflow_runtime_comparison.md)
  retains all 16 failed epic attempts and the successful fixture/control runs.
- **Live, bounded:** the corrected streaming harness passed one complete gate
  with real llama.cpp token output. The exact correction was also exercised by
  the longer request, which passed five complete loops and failed in loop 6.
  Three baseline API cases use real in-process TestClient lifespans; they are
  integration proof, not external network/model proof. Five focused tests passed.
- **Live native deterministic execution:** 4,100 ReviewRun repetitions passed,
  with strict replay parity and all five persisted-report validators passing.
  These runs made no model calls.
- **Structural provider proof:** the 120-turn stub soak passed. Service-load
  reports recorded 6,040 successful transport samples, but 40 background
  `CardNotFound` tracebacks prevent any completed-card claim.

The [long-run comparison](../../../benchmarks/staging/General/long_running_workflow_comparison.md)
contains timings, failed attempts, historical comparisons, exact source/evidence
hashes and native ownership receipts. Both staging reports were captured before
this commit; their references to an uncommitted state describe that historical
capture point. Their evidence bytes are retained unchanged. Git may normalize
text line endings; recorded source hashes identify the original working bytes.

Commit-time governance, targeted checks and branch/tag publication receipts are
retained under `.tmp/work-commit/`. Benchmark candidates remain in staging;
committing them is not approval to promote them to `benchmarks/published/`.

## What was not verified

No full suite/coverage campaign, new wheel installation, cross-platform proof,
completed 1,000-loop model endurance run, old-model rerun, statistical speedup,
real cold model reload or thermal endurance claim is added by this checkpoint.
The archived 30-page benchmark completed zero new runs because its retained Git
fixture lacks `HEAD`. A successful short streaming retry does not close the
long-run failure.

## Remaining blockers or drift

Stored epic team/acceptance issues, the temporary collection-board reference,
the streaming no-token/provider failure, synthetic service-trigger job errors
and the incomplete historical fixture remain as recorded in the comparisons.
Touched scripts retain seven pre-existing Ruff findings: two SIM105 findings
in the collection runner, and three E402 plus two SIM102 findings in the
streaming runner. New tests have no Ruff findings.

Architecture checklist AC-01 through AC-10 is satisfied for this bounded change:
scripts use existing contracts/owners, production decision and event schemas do
not change, actual effects and failures remain distinguishable, and the script
guidance and verification agree. This scoped review does not retire broader
architecture exceptions or prove whole-umbrella conformance.

PRR stays closed. PRR-S1 and broader architectural debt remain deferred under
the active architectural-truth umbrella. The October 6, 2026 00:00 Denver cutoff
and final six-hour reserve are unchanged. Task-owned commands settled; the
operator override, model server, provider, other worktrees and published releases
remain preserved.

## Exact files included

- `CHANGELOG.md`
- `pyproject.toml`
- `docs/releases/0.7.4/PROOF_REPORT.md`
- `examples/bug_fix/README.md`
- `examples/bug_fix/prepare.py`
- `examples/bug_fix/workflow.py`
- `examples/bug_fix/verify.py`
- `examples/bug_fix/seed/main.py`
- `examples/bug_fix/seed/test_existing.py`
- `scripts/README.md`
- `scripts/benchmarks/determinism_cli.py`
- `scripts/benchmarks/live_card_benchmark_runner.py`
- `scripts/benchmarks/live_rock_benchmark_runner.py`
- `scripts/benchmarks/run_determinism_harness.py`
- `scripts/benchmarks/run_live_card_benchmark_suite.py`
- `scripts/benchmarks/run_live_rock_benchmark_suite.py`
- `scripts/streaming/run_stream_scenario.py`
- `tests/scripts/test_benchmark_windows_command.py`
- `tests/scripts/test_stream_scenario_lifespan.py`
- `benchmarks/staging/General/stored_workflow_runtime_comparison.json`
- `benchmarks/staging/General/stored_workflow_runtime_comparison.md`
- `benchmarks/staging/General/long_running_workflow_comparison.json`
- `benchmarks/staging/General/long_running_workflow_comparison.md`
- `benchmarks/staging/index.json`
- `benchmarks/staging/README.md`

Ignored local execution evidence, generated databases and the operator's
skip-worktree override remain local under the existing preservation instructions.
