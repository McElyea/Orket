# Benchmark latency summary contract

Status: Active
Last updated: 2026-09-13
Owner: Orket Core

## Scoring authority

`scripts/benchmarks/score_benchmark_run.py` produces scored-report schema `v2`.
`scripts/benchmarks/benchmark_latency.py` owns duration aggregation and projection
validation, reusing the core finite nonnegative duration normalizer.

Per-task and overall `avg_latency_ms` are nullable. An average exists only when
the population is nonempty and every input run has a finite nonnegative numeric
`duration_ms`. Explicit numeric zero remains a reported zero. Missing, null,
boolean, string, negative, nonfinite or overflowing values do not establish a
duration. Partial coverage cannot lower the denominator or contribute invented
zeros. Empty populations have no average. Large finite durations are averaged
without overflowing an intermediate sum.

Both levels include `latency_summary`:

| Field | Meaning |
|---|---|
| `schema_version` | `benchmark_latency.v1` |
| `source` | `input_run.duration_ms` |
| `status` | `reported` for complete nonempty coverage, `partial` for some valid durations, otherwise `unavailable` |
| `samples_reported` | Count of valid numeric duration records |
| `runs_total` | Count of input run records |

`reported` means the input provided numeric durations. It does not prove a
monotonic clock, workload equivalence, independent measurement or historical
authenticity. Malformed task-detail objects, non-array run collections and
non-object run records fail instead of disappearing from coverage.

## Trends and dashboard

`report_benchmark_trends.py` validates v2 coverage metadata and its agreement with
the nullable average. Contradictions fail with
`E_BENCHMARK_LATENCY_SUMMARY_INVALID`. A latency delta exists only when both
adjacent reports provide complete reported averages. It remains an arithmetic
comparison; comparable workload/configuration proof belongs to capacity acceptance.

Historical or unknown scored schemas cannot establish that an old numeric average
excluded fabricated zeros. Their finite nonnegative number is preserved as
`legacy_avg_latency_ms`, while the current average/delta are null and the summary
status is `legacy_unverified`. Input reports are not rewritten.

`render_benchmark_dashboard.py` consumes the same validated projection and renders
missing/partial/legacy latency and unavailable deltas as `unavailable`. It preserves
reported numeric zero. Other score, cost, determinism and leaderboard contracts
retain their existing meanings; this repair does not verify those metrics.

## Commands and persistence

Existing CLI arguments and canonical output paths remain:

- `python scripts/benchmarks/score_benchmark_run.py`:
  `benchmarks/results/benchmarks/benchmark_scored_report.json`.
- `python scripts/benchmarks/report_benchmark_trends.py --inputs <scored reports>`:
  `benchmarks/results/benchmarks/benchmark_trends.json`.
- `python scripts/benchmarks/render_benchmark_dashboard.py --trends <trends> --leaderboard <leaderboard>`:
  `benchmarks/results/benchmarks/benchmark_dashboard.md`.

The JSON writers retain their shared rerun diff ledger. Source command execution
resolves the canonical `scripts` namespace from the checkout when needed; installed
proof uses copied script/test inputs and the declared installed core package.

## Raw harness admission

`run_determinism_harness.py` requires `--runner-template`; its former implicit
`orket run --task ...` command does not match the admitted CLI. Callers select an
explicit executable command. The default report path remains
`benchmarks/results/benchmarks/determinism_report.json` and valid-run schema
remains `1.1.3`, with the shared rerun diff ledger added.

`determinism_cli.py` validates the command arguments and selected task bank before
any runner launch or report replacement. Run count must be positive; task filters
must be nonnegative and ordered. The bank must be an array of task objects with
unique nonempty string or integer IDs (booleans are invalid). IDs normalize to
trimmed strings; numeric bounds require numeric IDs. The selected population must
be nonempty. Missing or blank templates and invalid admission exit 2 and preserve
an existing report. This admission does not validate arbitrary executable behavior
or prove bounded runner lifetime.

The harness averages actual run `duration_ms` records after this nonempty admission;
an empty task/run population cannot produce a successful zero-duration report.
Existing determinism, cost and telemetry meanings remain unchanged.
Repository-owned quant-sweep, canary and context-sweep Python handoffs use
`sys.executable` to retain the caller's installed dependencies. Operator-supplied
runner and sidecar templates retain their explicit executable choices.

## Prototype selection

`prototype_model_selector.py --summary <summary>` writes schema
`selector.prototype.v2` to the existing default path
`benchmarks/results/quant/quant_sweep/model_selector_prototype.json` with a shared
rerun diff ledger. Thresholds require finite `0 <= min_adherence <= 1` and finite
`max_latency >= 0`; invalid policy exits 2 before report replacement.

Candidates require the literal boolean `valid: true`, finite numeric adherence in
`[0, 1]`, and finite nonnegative numeric `total_latency`. Missing/null, boolean,
string, negative or nonfinite latency cannot satisfy a threshold. An explicitly
reported zero remains distinct from missing data and retains the existing zero
utility rule. Positive latency utility is adherence divided by latency; an
unrepresentable utility is rejected. Ranking remains utility, adherence, then
lower latency. `selected` is null when no candidate qualifies.

`rejected_candidates` retains model/quant identity and a reason: `run_not_valid`,
`adherence_unavailable`, `latency_unavailable`, `adherence_below_minimum`,
`latency_above_maximum` or `utility_unrepresentable`. Malformed summary collections
and missing model identity fail without replacing a retained report.
`measurement_posture: reported_unverified` identifies the evidence ceiling of
input metrics; selection is not proof of a real model run or independent timing.
Existing v1 reports remain historical inputs and are not rewritten in place.
