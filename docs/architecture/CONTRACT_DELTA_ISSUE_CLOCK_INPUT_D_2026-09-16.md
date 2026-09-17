# Issue-dispatch clock input

## Summary
- Owner: Orket Core.
- Date: 2026-09-16.
- Contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

## Delta
- Previously issue admission and closeout called an ambient application clock,
  independently of an explicitly supplied execution-pipeline clock.
- Issue-dispatch services require a UTC callable. Pipeline wiring passes its
  existing runtime input clock through the orchestrator. Direct orchestrator
  composition may supply that callable; its default remains the UTC adapter.
- Capture admission once and closeout only after acquiring the writer transaction.
  Borrowed transaction owners retain the same callable. Closeout effect, attempt
  end and released lease share that captured value, used unchanged.
  Earlier lease times remain refused with complete closeout rollback.
- This is explicit input ownership, not a monotonic wall-clock guarantee, automatic
  retry, or permission to rewrite historical records. Other clock paths remain D2.

## Migration Plan
1. Internal service constructors supply the UTC callable; no forwarding shim.
2. Ordered fixtures supply time explicitly. Retain exact historical reversed-time
   controls separately and preserve their prior artifacts.
3. Gates: real SQLite ordering/refusal/restart and transaction tests, pipeline
   composition, original prompt-compiler regression, installed affected matrix.

## Rollback Plan
1. Stop acceptance if composition drops the supplied clock or reversal publishes truth.
2. Repair clock propagation while retaining the lease and transaction invariants.
3. No persisted schema changes, mixed-writer migration, or history rewriting.

## Versioning Decision
- Development-candidate internal constructor change; no release/version bump yet.
- Effective upon implementation; acceptance status remains in the canonical plan.
- Embeddings constructing the issue service must provide `now_utc`.
