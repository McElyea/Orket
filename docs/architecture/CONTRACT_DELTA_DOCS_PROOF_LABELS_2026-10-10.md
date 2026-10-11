# Documentation proof-label alignment

## Summary
- Change title: align release evidence labels with the existing testing policy.
- Owner: Orket Core.
- Date: 2026-10-10 (America/Denver).
- Affected contracts: `docs/TESTING_POLICY.md`,
  `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`,
  `docs/specs/CORE_RELEASE_PROOF_REPORT.md`, `docs/CONTRIBUTOR.md`.

## Delta
- Previous wording: release policy called runtime execution `live`, while the
  testing policy required a real model and rejected provider-free runs.
- Current wording: release reports use the testing policy's existing definition.
  Provider-free CLI, installation and HTTP execution remain useful scoped
  contract/integration evidence. In the binary release `proof_mode` vocabulary,
  report them as `structural` and identify the actual executed scope; do not
  collapse real native execution into an import-only claim.
- Reason: the same observation must not acquire a stronger claim by moving
  from a test report to a release report. Required live proof remains required.

## Migration Plan
1. Effective for new or modified proof claims from 0.8.8. Historical records are
   preserved with their original candidate, commands and limitations.
2. Read historical labels together with their actual evidence; they do not
   establish current-checkout or model acceptance.
3. Validation: documentation/source review, generated authority checks and docs
   hygiene. This clarification does not change a runtime, test or verifier.

## Rollback Plan
1. Reconsider if a concrete release surface cannot express its evidence scope.
2. Revise the canonical policy and template together through another recorded
   delta; do not restore conflicting definitions silently.
3. No runtime state, stored artifacts or historical report bytes are migrated.

## Versioning Decision
- Version bump type: core patch, documentation-only.
- Effective version/date: 0.8.8 / 2026-10-10.
- Downstream impact: report authors use one live definition and retain explicit
  scope for non-live execution. SDK and runtime behavior are unchanged.
