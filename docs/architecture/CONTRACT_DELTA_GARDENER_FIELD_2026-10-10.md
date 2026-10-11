# Gardener field feedback contract delta

## Summary
- Change title: explicit governed model budgets and honest snapshot coverage.
- Owner: Orket Core.
- Date: 2026-10-10.
- Affected contracts: GOVERNED_AGENT_TASK_SUBMISSION, GARDENER_REPORT_HARNESS,
  PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT, PROVIDER_INFERENCE_CLIENT_OWNERSHIP.

## Delta
- Current behavior: Ollama context omitted, local CLI inventory used even for a
  different endpoint, report output silently capped at 512, governed history
  trimming and late budget refusal, standalone logging unbound on error paths.
- Proposed behavior: selected HTTP inventory; bound CLI logging; explicit input
  admission and output refusal; 2048 relevant profile ceilings; no governed
  message trimming or inference retries; native Ollama context and truncation
  guards; truncated receipts cannot certify reports. Captured HTTP ownership
  remains shared. SDK JSON response schemas now reach native structured-output
  fields; the report example supplies concrete generation constraints.
  Snapshot selection includes manifests/CI and permits explicit
  scopes; full inventory is retained with bounded prompt coverage metadata.
- Why now: field report and GitHub issues #3, #4 and #5 reproduced gaps in the
  released integration. Model-quality failures remain distinct from host defects.

## Migration Plan
1. Compatibility window: no implicit fallback. Governed Ollama requires >=0.24.0
   and observable model context metadata. Ordinary SDK streaming is unchanged.
2. Migration steps: reinstall the updated trusted report example; reduce selected
   evidence or explicitly configure both submission and host budgets. Capture
   bounds do not imply token capacity. Use WSL for full Gardener 0.3.0 align.
3. Validation gates: real Git/CLI/SDK/SQLite controlled-provider integration,
   retained native transport cleanup, actual model and Gardener dispatch with
   inspected receipts and owned server teardown. Record exact proof limitations.

## Rollback Plan
1. Rollback trigger: incompatible provider guards, ownership regression or false
   success classification.
2. Rollback steps: revert the candidate changes together; do not silently disable
   guards or claim that the original truncating path is verified.
3. Data/state recovery: retained runs remain inspectable/replayable; retry is a
   new run. No source writes or ledger migration are introduced.

## Versioning Decision
- Version bump type: core 0.8.2 patch for host fixes; no SDK wire/schema change.
- Effective version/date: 0.8.2, 2026-10-10. Release evidence and limitations:
  `docs/releases/0.8.2/PROOF_REPORT.md`.
- Downstream impact: old/unknown Ollama servers and oversized requests fail early;
  stronger snapshot defaults may require explicit scoping on large repositories.
  Successful report delivery still does not certify factual correctness.
