# Captured tool-result publication and owned file workers

## Summary
- Change title: Retain tool-result file workers through caller interruption.
- Owner: Orket Core.
- Date: 2026-09-17.
- Affected contracts: Governed turn dispatch ownership, result artifacts, protocol receipts and ordinary replay caches.

## Delta
- Current behavior: Protocol and ordinary result publication await plain thread futures. Caller cancellation can return while a file worker can still write. Nested arguments, results, binding metadata, execution capsule and timing context can change between publication steps.
- Proposed behavior: `turn_tool_result_persistence.py` captures result inputs and resolves required context values before its first await. Each admitted file worker uses the existing owned-I/O adapter and settles before cancellation or caller timeout returns. Repeated cancellation cannot release the enclosing turn owner early. A worker failure remains a failure, including failure observed while draining cancellation.
- Why this change is required now: Eighteen adverse filesystem/SQLite controls on unchanged 0.6.12 demonstrated borrowed-input drift and escaped workers. Four ordinary worker-error controls already refused publication. The separate retained Windows timeout identifies a location, not the cause of these controlled defects.

## Migration Plan
1. Compatibility window: Internal imports of `persist_protocol_operation` and `persist_non_protocol_tool_result_if_needed` move to `orket.application.workflows.turn_tool_result_persistence`; no forwarding shim is introduced.
2. Migration steps: Use the shared publication module from the dispatcher. Public tool arguments, file paths, receipt fields, hashes, replay semantics and control-plane schemas retain their contracts. Ordinary embedding without control-plane admission receives worker ownership, but gains no governed execution lock or effect-authority guarantee.
3. Validation gates: Captured nested inputs, concurrent isolated publications, actual file/SQLite failure and interruption controls, repeated cancellation, elapsed caller timeout, turn lock exclusion/reentry and unchanged receipt/replay behavior. Fresh source, installed artifacts, Windows/Linux Python envelopes and actual provider regressions remain required; evidence belongs in the canonical remediation plan.

## Rollback Plan
1. Rollback trigger: Required artifact or dispatch behavior cannot be preserved.
2. Rollback steps: Revert the extraction and its callers together; retain all failed and successful proof. Stop active writers before replacing code.
3. Data/state recovery notes: Files and control-plane publication remain separate effects. Cancellation after a file write can leave that artifact without a published step result. The dispatch marker remains unresolved and refuses redispatch; this change supplies no atomic multi-file transaction, historical repair or new reconciliation endpoint. Preserve those records for existing explicit reconciliation.

## Versioning Decision
- Version bump type: Patch checkpoint destined for main, with a matching local annotated tag after verification.
- Effective version/date: 0.6.13 local checkpoint, 2026-09-18.
- Downstream impact: Migrate the two internal imports. Cancellation latency includes the lifetime of an already admitted file worker; an unresponsive worker can delay cancellation indefinitely. This change does not claim forced thread termination, general async conformance, OS containment, complete input replay or atomic file/control-plane publication.
