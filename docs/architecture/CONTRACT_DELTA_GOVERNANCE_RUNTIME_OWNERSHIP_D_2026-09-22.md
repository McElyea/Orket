# Contract delta: governance proof runtime ownership

Date: 2026-09-22
Change classification: breaking
Runtime modes: all
Migration requirement: required

## Contract

`docs/specs/SCRIPT_RUNTIME_OWNERSHIP.md` now also governs the three truthful-runtime
proof recorders. They refuse event-loop entry before native effects and acquire their
engines inside the existing async lifetime owner. Construction, execution and cleanup
settle before command return. Existing proof payloads and runtime-success checks are
unchanged. A missing card remains a refusal when interruption arrives during cleanup;
cleanup failure remains visible and cannot yield success.

Packet 1 always restores environment overrides, including failed alias cleanup. It
preserves pre-existing aliases, removes only one successfully created by its own
invocation and surfaces nonzero removal. Alias ownership is process-local; it is not
cross-process fencing, ambiguous-copy recovery or child-process supervision.

## Migration

- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`

Call native recorders outside an active event loop. Private async proof scopes accept
configuration and database paths and acquire their engine instead of borrowing a
preconstructed one. No compatibility shim or acceptance fallback is added.

## Verification and limits

Actual local HTTP failure, real engine and SQLite cleanup, repeated cancellation,
timeout and cleanup failure exercise resource lifetime. Simulated alias command
responses prove only the command contract and environment restoration. Retained
counterexamples and source/installed binding belong to the canonical plan. No actual
Ollama alias acceptance, Linux clock acceptance, full D/E/CAP completion or retirement
is implied. Existing deadlines, BT gates and proof schemas remain unchanged.
