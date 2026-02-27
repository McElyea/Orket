# Bottleneck Thresholds (Transitional)

Last reviewed: 2026-02-27

This document is retained as operator guidance only.
There is no single canonical runtime contract in Orket that enforces all threshold values listed here.

## Guidance
1. Treat resource queue growth as a trend metric, not a single-point alarm.
2. Tune thresholds per hardware profile and workload pattern.
3. Prefer deterministic gate checks for release decisions over ad-hoc threshold alerts.

## Suggested Starting Points
1. Local workstation:
   - normal queue: `<= 3`
   - warning queue: `4-10`
   - critical queue: `> 10`
2. Multi-GPU host:
   - scale thresholds by expected parallel slots.

## Canonical Gate Documents
1. `docs/TESTING_POLICY.md`
2. `docs/BENCHMARK_DETERMINISM.md`
3. `docs/QUANT_SWEEP_RUNBOOK.md`

If this guidance becomes implementation policy, move exact thresholds into a contract-backed doc and tests.
