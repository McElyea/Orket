# Provider phase timing and SDK generation availability

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Authority: `docs/specs/MODEL_PROVIDER_TIMING.md`.
- Scope: provider phase observations, turn/benchmark projections and public SDK
  generation latency; BT-4 remains the gate owner.

## Delta
- Previously absent backend phases became zero or an inferred portion of total
  time, and absent total could become client elapsed time. New versioned provider
  timing retains each missing/invalid field as null, without phase inference.
- Client elapsed remains separate with its actual source and successful-attempt
  scope. Neither failures nor missing backend observations fabricate timing.
- Legacy numeric projections retain unverified provenance. Benchmark aggregates
  require complete reported timing across every included turn and complete token
  coverage for throughput; partial coverage cannot become complete evidence.
- SDK generation latency becomes nullable with explicit response version/posture.
  Null/static providers do not claim a measured zero. The generic API preserves
  the nullable SDK response instead of unconditionally converting it to int.

## Migration Plan
1. Use the paired SDK 0.7.0a1 and host development artifacts. Review generic
   `model.generate` consumers for nullable latency and version/posture handling.
2. Retain original provider observations, logs and old benchmark artifacts.
   No historical timestamp, measurement, phase or provenance is reconstructed.
3. Source counterexamples, projection/aggregate controls, matched installed
   packages and actual llama.cpp/API/CLI proof must precede slice acceptance.
   Exact results and outstanding gates belong to the canonical remediation plan.

## Rollback Plan
1. Preserve retained records and package hashes. If a consumer cannot handle
   unavailable timing, stop affected new admission while repairing that consumer.
2. Do not restore zero/inferred phases, relabel old observations as new-schema
   evidence, or recertify old aggregate outputs to make a consumer pass.

## Versioning Decision
- First explicit provider timing and SDK generation-response schema markers;
  independently versioned governed-agent receipts remain v2.
- The existing unpublished SDK minor prerelease includes this contract change.
  Published compatibility and core release/tag rules remain unchanged.
