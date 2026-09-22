# Captured outbound policy inputs and owned file observations

## Summary
- Change title: Bind immutable policy before API admission and Kernel projection
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-22
- Affected contracts: outbound policy loading, gate input ownership, API preparation and projection
- Status: Implementation contract; acceptance remains in the canonical plan
- Durable authority: `docs/specs/OUTBOUND_POLICY_INPUTS.md`

## Delta
- Before: frozen gates retain mutable field mappings; file loading performs direct
  unguarded reads; API filtering reads process policy environment after construction;
  projection can sample policy after a clock callback and separately for its contexts.
- After: pure immutable policy values feed explicit evaluation; a classified read-only
  adapter performs selected file reads in native execution. API preparation binds
  one validated policy; projection captures one policy before observation callbacks.
- Missing/invalid file observations remain failures, and malformed patterns fail
  before API admission. Acquired resources close even when preparation is interrupted.

## Migration
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Rebuild the app to change outbound file/environment configuration; do not mutate
  app policy state or caller-owned gate mappings to reconfigure a running app.
- Use owned native workers for policy-file loading. Select absolute paths or a bound
  invocation root; do not rely on a later cwd change to select the file.
- Supply valid string sequences/mappings to typed inputs and gate constructors.
  Fix malformed patterns before startup; handle explicit input/native failures.
- Use `policy_inputs` for deterministic evaluation without ambient fallback.

## Verification and limits
Acceptance requires retained pre-change failures, real source/installed API and
filesystem observations, immutable input parity, cancellation/timeout/failure cleanup,
independent responsiveness and unchanged BT ledger-disclosure behavior. This does
not claim regex worst-case bounds, arbitrary PII completeness, file containment,
external provider acceptance, complete D implementation or lane retirement.
