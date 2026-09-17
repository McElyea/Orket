# Protocol contract and ledger ownership

## Summary
- Owner: Orket Core.
- Date: 2026-09-17.
- Affected contracts: architecture dependency/effect boundaries, protocol hashing,
  invocation and result/error vocabulary, and first-operation commit storage.

## Delta
- Protocol hashing, tool-invocation contracts, error codes and result/error
  invariants move from runtime into `orket/core/contracts/`. Runtime and adapter
  consumers import the same canonical pure definitions.
- `OperationCommitRegistry` moves into storage adapters. Every persisted read or
  commit reloads under native local ownership. Independent cooperating writers
  cannot replace a retained first winner through stale in-memory state. A busy
  owner causes explicit refusal; callers may retry after it releases ownership.
- New winners are published in memory only after a same-directory temporary
  write, file flush/fsync, atomic replacement and byte verification. Missing files
  start empty; malformed JSON, invalid row structure, duplicate operation rows and
  invalid event sequences refuse mutation and preserve the original file.
  Event sequences must be positive integers, excluding booleans; strings and
  fractional values are no longer coerced. Storage refusals use the registered
  `E_OPERATION_REGISTRY:<detail>` family; underlying I/O failures propagate.
- Protocol ledger file workers remain owned through cancellation and timeout.
  The repository lock stays held until the admitted worker finishes. Receipt,
  custom-event, start-summary and final-summary inputs are copied before the first
  await. Receipt file I/O has a dedicated storage owner.

## Migration Plan
1. Replace internal imports of `orket.runtime.registry.protocol_hashing`,
   `tool_invocation_contracts`, `protocol_error_codes` and
   `orket.runtime.policy.result_error_invariants` with their names under
   `orket.core.contracts`. Import `OperationCommitRegistry` from
   `orket.adapters.storage.operation_commit_registry`.
2. Existing root/application compatibility aliases point to the new owners; their
   existing removal scope is unchanged. No new compatibility shim is introduced.
3. Valid existing `{"entries": [...]}` registry files retain their format and
   first-winner semantics. Preserve corrupt files for investigation; do not reset
   them or silently drop rows to make a new commit succeed. Preserve the adjacent
   `<registry>.owners/` native ownership files with live storage.
4. Require source and installed Windows/Linux Python 3.11/3.12 protocol and prior
   C/D regressions, independent process contention, retained-worker interruption,
   package parity and the separate installed llama.cpp regression envelope.
   Exact results and artifacts belong to the canonical remediation plan.

## Limits and Rollback Plan
- This is cooperating local-file ownership, not hostile pathname fencing,
  authenticated historical evidence, power-loss recovery or a transaction across
  event, receipt, commit-registry and derived run-graph files. Receipt concurrency
  across independent repository instances is outside this proof.
- Cancellation waits for an admitted worker; it does not kill a permanently stuck
  worker. Multi-file operations can retain partial derived artifacts and must not
  claim atomic completion merely because one worker finished.
- Registry reads may create/acquire ownership files. They do not rewrite retained
  winner data. Event schemas, hash algorithms and CLI arguments remain unchanged.
- Preserve a failing artifact and repair the canonical boundary on regression.
  Do not restore silent corruption recovery or reverse dependency shims.
- Remaining C/D, quality, capability and whole-lane gates stay active.

## Versioning Decision
- Core patch checkpoint `0.6.4`; SDK remains `0.7.0a1`.
- Internal import and invalid-input compatibility is breaking; valid persisted
  registry format and protocol wire/hash contracts are preserved.
