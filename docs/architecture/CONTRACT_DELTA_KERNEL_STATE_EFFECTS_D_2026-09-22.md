# Kernel local state input and effect boundaries

## Summary
- Change title: Captured LSI inputs and owned native state effects
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-22
- Affected contracts: LSI staging/read/validation, promotion and ledger repair
- Status: Implementation contract; acceptance remains in the canonical plan
- Durable authority: `docs/specs/KERNEL_STATE_EFFECTS.md`

## Delta
- Before: direct LSI retains a relative root; staging reuses borrowed values after
  writes; direct state operations can block an event loop. Filesystem mechanics
  and path/reference definitions are duplicated. Missing staging can delete all
  committed triplets despite the historical no-op requirement.
- After: captured roots and immutable staging bytes feed a shared classified
  filesystem adapter. Native state effects refuse event-loop execution. Missing
  or empty staging advances only the ledger; actual deletion needs a tombstone.
- Invalid lexical paths and observed index/cleanup failures refuse or report
  failure explicitly. Multi-step directory publication remains non-transactional.

## Migration
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Use owned native workers for direct state effects and retain them through close.
- Construct a new LSI instance to select another root; the captured root is read-only.
- Supply valid names within the state namespace. Do not use missing staging to
  request deletion; stage explicit valid tombstones instead.
- Handle explicit index-read/cleanup failures; do not infer rollback from refusal.

## Verification and limits
Acceptance requires retained pre-change counterexamples, deterministic input-plan
parity, actual filesystem effects and no-op preservation, source/installed matching
cases, native-failure paths and interruption responsiveness. No new hostile-path
containment, external-writer safety, crash atomicity or full-lane acceptance claim.
