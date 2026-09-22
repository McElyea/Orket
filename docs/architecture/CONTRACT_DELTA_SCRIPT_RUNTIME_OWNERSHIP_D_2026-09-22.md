# Contract delta: script runtime and replay observation ownership

Date: 2026-09-22
Change classification: breaking
Runtime modes: all
Migration requirement: required

## Contract

`docs/specs/SCRIPT_RUNTIME_OWNERSHIP.md` governs ProductFlow command engine
lifetime and replay audit resource observation. The shared ProductFlow operation
owner retains the existing builder and closes acquired engines before returning.
Witness campaign execution and collection share one event loop. Artifact replay
uses the native diagnostics service without a runtime, through an owned worker.
Direct diagnostics from a running event loop now refuse before filesystem work.
Default audit model-provider construction and cleanup use an explicit resource owner.

Real command proof also requires migrating ProductFlow's stale seat-policy callback
and declaring canonical exact-output artifact acceptance. Witness construction
selects retained resource history bound to the checkpoint's lease and refuses a
missing match; later turns cannot replace that witness. The witness and substrate
specs clarify this selection. Their verifiers and BT approval/completion gates are
unchanged; no success condition or deadline is relaxed.

## Migration

- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`

Native diagnostics callers remain valid; async callers use an owned worker.
Commands use the shared ProductFlow operation owner. Borrowed-engine lower-level
operations retain their caller-owned contract. Injected replay callables own their
resources. No module shim, replay authority change or model substitution is added.

## Verification and limits

Actual engine/resource cleanup, artifacts, SQLite responsiveness and controlled
HTTP transport exercise the changed paths. Counterexamples, interruption/failure
proof and source/installed binding are recorded in the canonical plan. Fixtures
are not actual inference. Linux, full D/E/CAP acceptance and lane retirement remain open.
