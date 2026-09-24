# Guard-request clock and publisher selection

## Summary
- Change title: Retain explicit guard-request time and admitted publisher ownership.
- Owner: Orket Core.
- Date: 2026-09-23.
- Affected contract: `docs/specs/EPIC_RUNTIME_TIME_INPUTS.md`.
- Status: 0.6.103 implementation migration. Acceptance and publication belong to
  the architectural-truth plan and its checkpoint receipts.

## Delta
- Current behavior: published .102 samples ambient UTC and selects the reservation
  publisher after awaiting the durable pending row. Matched corrected source and
  installed openings show four failures and two healthy controls per cell. The
  prior opening's public-route fixture failure remains separate, with no route claim.
- Proposed behavior: preserve synchronous policy resolution, sample the existing
  pipeline-selected clock once, and capture the publisher object before awaiting
  the existing pending repository. Publish the hold through that captured object
  using the returned request ID and the same timestamp.
- Preserved behavior: gate policy, pending identity, row-before-hold ordering,
  selected missing/None publisher, schemas and BT-1 through BT-5 authority. Required
  method lookup remains after the row. Malformed present publishers and later
  persistence failures propagate while the row remains; no retry or rollback.
- Why required now: reached D counterexamples show observable ambient time and
  redirection to replacement publisher B, even when the admitted publisher is None.

## Migration Plan
1. Compatibility window: no API or schema change; existing construction already
   supplies the clock. No fallback clock, publisher or second resource owner.
2. Migration steps: change only request time selection and publisher capture in the
   existing helper; retain the public-handler route and repository/service owners.
3. Validation gates: preserve both matched openings, exact selected timestamp and
   admitted-owner controls, healthy publisher/None behavior, malformed-present and
   later-failure durable prefixes, exact-one save attempt, SQLite <0.5s, canonical C,
   and frozen source plus installed Windows acceptance with all prior case identities.

## Rollback Plan
1. Rollback trigger: accepted behavior drift, row-prefix loss, redirected publication,
   package mismatch or failed acceptance.
2. Rollback steps: keep a failed candidate unpublished; correct under a fresh proof
   phase or revert the bounded helper and corresponding authority change together.
3. Data/state recovery notes: retain all observations and any published rows. This
   migration does not automatically retry, repair, delete or accept historical state.

## Versioning Decision
- Version bump type: compatible patch within the active 0.6 remediation lane.
- Effective version/date: 0.6.103, subject to required verification and publication.
- Downstream impact: controlled clocks now govern this request path. Publisher
  object capture does not snapshot its internal mutable state. No new cancellation,
  full-epic/provider, Linux, atomicity, full-coverage or lane-completion claim.
