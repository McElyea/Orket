# Review preflight selected time

## Summary
- Change title: Explicit review support and note time.
- Owner: Orket Core.
- Date: 2026-09-27.
- Affected contract: `docs/specs/EPIC_RUNTIME_TIME_INPUTS.md`.

## Delta
- Review preflight previously read host UTC for support history, and `Note`
  independently read host UTC for both identity and creation time. These bypassed
  the standard engine's selected clock.
- Composition supplies the existing `turn_clock`; preflight captures its callable
  before verification awaits. Support publication samples after verification, and
  each note samples after its associated state/verification publication. Its
  timestamp-shaped id and `created_at` share that explicit value.
- Note values perform no ambient clock observation. Existing support-only authority,
  retry/terminal decisions and final card acceptance remain unchanged.
- Each selected support/note observation requires a timezone-aware `datetime` and
  normalizes its explicit offset to UTC. Strict validation refuses naive and
  non-datetime values before the affected publication, preventing timestamp-shaped
  note identity from consulting the host timezone. A later note refusal does not
  roll back an earlier support artifact or state transition.

## Migration Plan
1. Direct preflight constructors supply `utc_now`; the composed caller forwards
   the existing clock, returning aware datetime values. Direct `Note` callers
   supply `id` and `created_at`.
2. Complete serialized notes need no rewrite. Notes are ephemeral; no historical
   timestamps are synthesized or durable ledger schemas changed.
3. Real engine controls use a declared model fixture and synthetic selected clock,
   inspect retained successful/failed support history and failure notes, and retain
   existing review and empirical-verification guards. Explicit non-UTC clocks and
   invalid support/note samples exercise real engine publication/refusal paths.
   Model responses and selected clock values are declared fixtures, not live inference.

## Rollback Plan
1. A clock propagation or outcome parity failure blocks acceptance.
2. Revert caller and value-contract changes together if necessary; retain all
   published support records and their actual timestamps.
3. Restoring implicit clocks restores the known input defect, not deterministic
   conformance. Note ids remain timestamp-shaped and do not claim uniqueness.

## Versioning Decision
- Version bump type: patch checkpoint with explicit internal constructor migration.
- Effective date: 2026-09-27 candidate; publication belongs to the active plan.
- Downstream impact: direct internal constructors require explicit time inputs;
  stored support format, card status and completion authority are preserved.
