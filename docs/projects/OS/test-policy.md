# OS Test Policy

Last updated: 2026-02-22
Status: Normative

## Required Gates
1. All OS contract fixtures validate against JSON schemas.
2. Replay fixtures are required for deterministic contract changes.
3. Promotion atomicity tests are required for state transition changes.
4. Fail-closed diff behavior must remain enforced.
5. No partial commit behavior must be verified.
6. RFC6901 pointer format checks must pass for emitted locations.

## PR Must Fail If
1. Contract shape changes without version bump.
2. A required error code is removed or renamed without migration note.
3. Canonicalization behavior changes without version bump.
4. Nondeterministic ordering is introduced in contract outputs.
5. Unknown plugin events pass through without schema validation failure.

## Required Test Families
1. `tests/contracts/*` for schema and policy contracts.
2. `tests/kernel/v1/*` for kernel interface compatibility.
3. Fire-drill scenarios for triplet, policy, determinism, orphan-link checks.
