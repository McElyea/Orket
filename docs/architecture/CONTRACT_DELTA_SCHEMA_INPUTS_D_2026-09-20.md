# Explicit schema inputs

## Summary
- Change title: Core values require identities and reject unknown environment keys
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-20
- Affected contract: `docs/specs/SCHEMA_INPUT_OWNERSHIP.md`

## Delta
- Previous behavior: card/scenario model defaults generated UUIDs, including
  nested model validation. Environment construction warned and dropped extra keys.
- Proposed behavior: identities are explicit core inputs; authored asset admission
  obtains them from the application runtime input service. Environment extras fail
  without warning effects. Authoritative environment helper error codes remain.
- Required now to remove ambient effects from core schema validation while keeping
  identity-free authored asset loading supported at its actual application owner.

## Migration Plan
1. Effective in the scoped 0.6.45 candidate; no implicit core-ID compatibility shim.
2. Direct core constructors supply IDs. Authored asset callers use the application
   factory or `ConfigLoader`; stored accepted values retain their existing IDs.
   Remove unknown environment keys instead of relying on warn-and-drop behavior.
3. Validate pre-change counterexamples, nested aliases, preserved explicit values,
   generation failure, JSON-mode parity, real file loading/prompt commands, affected
   runtime regressions and installed package origins. Proof status stays in the
   active architectural-truth plan until observed.

## Rollback Plan
1. Roll back the scoped implementation and callers together if authored admission
   changes accepted runtime/effect behavior or loses identity associations.
2. Restore the matching source of truth and retain all failure receipts.
3. No durable record rewrite occurs. Do not regenerate IDs in accepted records.

## Versioning Decision
- Version bump type: patch remediation checkpoint with an explicit breaking delta.
- Effective version/date: 0.6.45 candidate / 2026-09-20.
- Downstream impact: direct constructors require IDs; environment extras now fail.
