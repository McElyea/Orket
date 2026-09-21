# Captured execution identities and scalar naming inputs

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.51 candidate, 2026-09-20.
- Durable contract: `docs/specs/EXECUTION_IDENTITY_INPUTS.md`.

## Delta and migration
Epic/collection setup previously selected IDs after awaited asset reads and passed
a sanitizer callable into build strategy. Application now observes missing IDs,
computes the authoritative sanitized name and admits selected string IDs before
the first setup/collection asset read. Custom build methods accept a sanitized
string instead of invoking a callback. Both original and sanitized names remain
available; default prefixes and explicit build overrides are unchanged.

Selected IDs must be nonempty plain strings. A later read failure may follow an
already-consumed ID observation; earlier pipeline initialization is not erased.
This does not freeze child configuration or the complete public pipeline. Existing
admission/recovery/completion ownership remains unchanged and no hostile-code
containment is claimed.

## Verification and rollback
Retain held actual asset-read controls for epic and collection identities and the
scalar-versus-callable probe. Check published default outcomes, strict early
refusal, real SQLite publication, child outcomes and installed caller behavior.
Record actual live paths and platform blockers in the canonical plan.

Rollback callers and custom strategy signatures together, preserving historical
session/build IDs and publication evidence. No compatibility retry is introduced.

## Versioning decision
- Patch remediation checkpoint with an explicit breaking build-strategy input delta.
- Remaining D input/effect work, E/CAP and whole-lane acceptance stay open.
