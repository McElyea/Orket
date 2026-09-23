# Packet-2 receipt and audit ownership

## Summary
- Change title: Capture packet-2 inputs and retain native receipt/audit work.
- Owner: Orket Core.
- Date: 2026-09-22.
- Affected contracts: `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`
  and `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`.

## Delta
- Current behavior: protocol discovery and file-audit metadata can block the event
  loop; an interrupted receipt open can outlive its caller. Policy, provenance and
  relative workspace use can observe caller changes after receipt collection starts.
- Proposed behavior: capture the lexical absolute workspace, normalized policy and
  detached provenance before the first await. Reuse the existing native owner for
  discovery, native receipt read/decode/close and file audit. Cancellation and caller
  timeout drain admitted native work before returning, without admitting later steps.
- Why this break is required now: matched source and installed v0.6.98 controls
  reproduce blocked independent SQLite work, changed workspace selection and early
  interrupted return. Existing source-attribution ownership does not cover its caller.
- Preserved semantics: protocol-file precedence per turn, receipt ordering, legacy
  operation identities, tolerated read/JSON failures, governed references, successful
  effect admission and card-history authority. File audit verifies existence and
  containment, not semantic content. Source-attribution sufficiency is unchanged.
- Limits: mutable observations are not an atomic snapshot; no rollback, forced
  native termination, hard filesystem deadline or handle-bound confinement is added.

## Migration Plan
1. Compatibility window: v0.6.99 adopts retained interruption immediately; no shim
   or parallel receipt authority. Stored receipt and summary schemas are unchanged.
2. Migration steps: retain interrupted collection callers until native settlement.
   Supply intended inputs before starting the async body; later caller mutation
   cannot revise an admitted collection. Preserve existing receipts and evidence.
3. Validation gates: matched opening controls; actual filesystem/SQLite responsiveness,
   captured-input, cancellation/timeout and parity regressions; fresh source and
   installed Windows 3.11/3.12 matrix, package parity and canonical dependency gate.
   Linux clock and wider D/E/CAP acceptance remain separately recorded obligations.

## Rollback Plan
1. Rollback trigger: changed receipt precedence, identity, classifications or ownership.
2. Rollback steps: stop relying on affected summaries and repair forward through the
   same collector and resource owner. Do not restore abandoned native operations.
3. Data/state recovery notes: observation does not rewrite receipts, artifacts or
   card history. Preserve all failed and passing evidence; no resealing or deletion.

## Versioning Decision
- Version bump type: patch; scoped architectural remediation.
- Effective version/date: 0.6.99 / 2026-09-22.
- `compatibility_status`: `breaking`.
- `affected_audience`: `all`.
- `migration_requirement`: `required`.
- Downstream impact: cancellation/timeout completion waits for native settlement;
  mutable invocation inputs are captured. Public result vocabulary stays unchanged.
