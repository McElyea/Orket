# Benchmark runner and selector admission

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Authority: `docs/specs/BENCHMARK_LATENCY_SUMMARY.md`.
- Trigger: empty tasks and zero runs produced successful zero-duration reports;
  missing selector latency became zero and qualified under a strict threshold.
  The raw harness also defaulted to an unsupported `orket run --task` invocation.

## Delta
- Require an explicit runner, positive runs and valid nonempty task selection
  before launching a child or replacing a report. Invalid admission exits 2.
- Selector v2 refuses missing/invalid latency and invalid thresholds, explains
  rejected candidates and labels reported inputs as unverified measurements.
- Preserve explicit reported zero, existing valid-run metrics and output paths;
  both JSON writers now use the canonical rerun diff ledger.
- Keep internal quant/context Python subprocesses in the caller's environment.
  Windows proof exposed bare `python` selecting the base interpreter without
  declared project dependencies despite the active environment leading PATH.

## Migration Plan
1. Supply `--runner-template` for raw harness calls. Existing suite and quant-sweep
   callers already supply their templates; no compatibility alias is added.
2. Consume selector v2 rejection reasons and nullable selection. Retain v1 history
   without treating absent metrics as successful measurement.
3. Preserve the original failed CLI observations and compare repaired commands
   with a real controlled runner. The Gitea quant-sweep workflow covers admission.

## Rollback Plan
1. Stop unsupported benchmark admission or model selection while retaining reports.
2. Do not restore empty successful runs or invented duration values to regain a
   numeric result. Retain original evidence and rerun history.

## Versioning Decision
- Selector schema advances from `selector.prototype.v1` to `selector.prototype.v2`.
  Valid raw-run report schema remains `1.1.3` with additive diff-ledger metadata.
- Core/SDK artifacts are unchanged. No release or capacity acceptance is implied.
