# Benchmark scored-report latency availability

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Authority: `docs/specs/BENCHMARK_LATENCY_SUMMARY.md`.
- Trigger: absent durations became zero and lowered partial-run averages through
  scoring, trends and dashboard output.

## Delta
- Scored schema v2 includes nullable averages and versioned duration coverage.
  Only complete nonempty finite numeric input supports an average.
- Historical/unknown scored schemas retain their numeric values as unverified
  history. Current comparisons cannot promote them into timing evidence.
- Trend and dashboard readers share coverage validation. Unavailable timing is
  explicit in human output; malformed current metadata fails.

## Migration Plan
1. Update scored-report consumers for schema v2, nullable `avg_latency_ms` and
   `latency_summary`. Existing v1 reports remain unchanged.
2. Re-score retained per-run inputs to establish current coverage. Preserve the
   existing rerun diff ledger and distinguish reported values from measured proof.
3. Keep latency acceptance separate from score thresholds and comparable-workload
   capacity claims. Preserve the original missing/partial-run counterexamples.

## Rollback Plan
1. Stop latency comparisons when coverage cannot be established.
2. Retain reports and failed observations; do not restore fabricated zeros to
   recover numerical output.

## Versioning Decision
- Scored-report schema advances from v1 to v2; coverage uses benchmark_latency.v1.
  Core and SDK packages are unchanged by this script-only behavior repair.
- No release, tag, publication or broader benchmark/capacity acceptance occurs.
