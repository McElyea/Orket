# Shared execution state revisions

## Summary
- Change title: Compare observed revisions before run, attempt and step mutation.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contracts: ControlPlane execution repository and
  `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

## Delta
- Previous behavior: Immutable run identity was checked, but an independent
  stale writer could overwrite completed state. A real completed step could also
  be replaced by its earlier dispatch marker.
- New behavior: `state_revision` is null only for creation. Stored revisions begin
  at zero; changed writes compare the observed revision and advance it atomically.
  Identical current writes are no-ops. Stale revisions and blind recreation fail.
  Python value validation precedes serialization; Boolean revisions are invalid.
  Applications use the returned record, and attempt/step admission stays immutable.
  The initial CREATED-to-EXECUTING attempt transition may set its execution start
  timestamp; later writes cannot change that timestamp or the starting snapshot.
- Kernel pre-effect rejection/error now retains valid abandonment with failure
  evidence only in its recovery decision. Views verify the decision binding and
  project recovery failure fields separately from the null attempt failure fields.
- Reason: Shared mutable persistence must preserve the state accepted by the
  existing application authority, including changes away from and back to a value.

## Migration Plan
1. Stop old writers before deployment. New readers expose missing historical
   revisions as zero without backfill; explicit persisted null is refused.
2. Only an admitted changed write persists an advanced revision. Historical
   execution and closure still require their existing authority and reconciliation.
3. Prove stale writers, independent connections/processes, rollback/cancellation,
   historical reads and real composed family behavior in source and installed
   environments. Current acceptance status stays in the canonical plan.

## Rollback Plan
1. Stop admission on false publication, lost state or required-path regression.
2. Preserve stores and counterexamples; do not restore a permissive older writer.
3. No downgrade, history reset or synthesized effect is a recovery mechanism.

## Versioning Decision
- Add `state_revision` to existing execution record schemas in the unreleased
  core 0.6.2 candidate. Older strict readers reject the new field.
- No release, commit, tag, mixed-version writer support or remote fence is implied.
