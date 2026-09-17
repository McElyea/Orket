# Card Acceptance Definition Admission

## Summary
- Change title: Reject acceptance authority embedded in model structural proposals.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and
  `docs/architecture/event_taxonomy.md`.

## Delta
- Opening behavior: the model driver writes complete proposed epics/rocks,
  including nested completion definitions, into selected runtime configuration.
  Builtin card creation silently ignores the same supplied parameter.
- Required behavior: shared pure core policy rejects the reserved
  `completion_acceptance` member in nested model JSON before structural or card
  storage writes. The driver returns an explicit error without a success suffix
  and records `driver_process_failed` with `failure_kind=acceptance_admission`.
  Builtin creation returns the same stable error code in its tool result.
- Reason: authoring the objective does not admit model-chosen completion criteria.
  Trusted application/operator configuration remains the existing input boundary.
  Ordinary model-created cards have no implicit acceptance. This change adds no
  public admission endpoint, serialized trust flag or historical provenance claim.

## Migration Plan
1. No compatibility window permits new model definitions through these paths.
2. No schema migration or rewriting of existing configurations/receipts. Existing
   file authorship is not inferable from deserialized criteria; custom and
   privileged writers remain outside this scoped proof.
3. Validate all three structural actions, nested and legacy child shapes,
   unchanged asset bytes, explicit builtin refusal, and non-completion for cards
   without criteria. Exercise a real provider response through the driver.

## Rollback Plan
1. Trigger: rejection of ordinary non-authority data or writes occurring on refusal.
2. Correct the boundary while preserving fail-closed treatment of model criteria.
   Retain the failing response and asset hashes for review.
3. No production state was migrated or historical proof resealed in this change.

## Versioning Decision
- Effective date: 2026-09-12; no release, commit or version bump in this checkpoint.
- Existing definition/receipt schemas are unchanged. Clients must handle the
  explicit rejection instead of relying on ignored or model-admitted definitions.
