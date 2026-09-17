# Generic model generation request options

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Authority: `docs/specs/MODEL_GENERATION_OPTIONS.md` and the canonical local
  prompting contract.
- Trigger: a real API request specified 512 tokens but its backend reported 593.

## Delta
- The builtin SDK adapter now forwards its request options to the shared policy.
  Limits narrow a resolved profile; unresolved admitted profiles retain explicit
  options instead of discarding them.
- Per-call temperature and exact stop strings reach provider payloads. Identical
  stops deduplicate without whitespace normalization. Empty strings fail before
  inference instead of being silently removed.
- Option validation also applies before unresolved profile return. Partial
  sampling bundles map only their present fields; absent options do not become
  invented profile defaults.
- Custom profile stop lists share the core exact-string validator with request
  options. Profile loading/binding preserves whitespace and rejects invalid elements.

## Migration Plan
1. Use the matched core development candidate and existing SDK 0.7.0a1. Request
   defaults now apply per call; callers must supply their intended options.
2. Repair invalid context producers instead of coercing malformed limits into
   measurements or silently dropping stop strings. Existing interface numeric
   parsing/bounds and strict-profile refusal are retained.
3. Preserve prior contradictory results. Retain transport controls, installed
   regression proof and separate live limit/stop evidence in the canonical plan.

## Rollback Plan
1. Retain source/artifact identities and failed observations. Stop affected
   admission if a consumer/backend cannot honor required options.
2. Do not restore silent option loss, widen a profile ceiling or certify an
   unverified backend merely because its request payload looks correct.

## Versioning Decision
- Core host behavior repair within the current unreleased candidate; no SDK wire,
  response schema, release or tag changes.
- No broader provider, native payload override or workload acceptance claim.
