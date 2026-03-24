# Contract Delta Proposal

## Summary
- Change title: Control-plane lease publication identity and sandbox lease truth wiring
- Owner: Orket Core
- Date: 2026-03-23
- Affected contract(s): `orket/core/contracts/control_plane_models.py`, `orket/core/contracts/repositories.py`, `docs/projects/ControlPlane/orket_control_plane_packet/01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md`, `docs/projects/ControlPlane/orket_control_plane_packet/05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: `LeaseRecord` exists as a first-class noun, but it has no publication identity and the default sandbox runtime does not publish durable lease truth; lease state remains implicit inside sandbox lifecycle rows.
- Proposed behavior: `LeaseRecord` gains `publication_timestamp` so lease truth can be published as append-only snapshots, and the default sandbox runtime publishes sandbox lease history into the control-plane durable store across initial claim, active ownership, renewal, reclaimable expiry, lost-runtime uncertainty, and verified cleanup release.
- Why this break is required now: without a publication identity, lease history cannot be stored truthfully without overwrite or synthetic duplicate nouns, and the ControlPlane lane would keep claiming first-class lease authority while runtime behavior stayed adapter-local.

## Migration Plan
1. Compatibility window: immediate for control-plane callers that construct `LeaseRecord` directly.
2. Migration steps:
   - add `publication_timestamp` wherever `LeaseRecord` is instantiated
   - use the control-plane publication service for new durable lease writes
   - consume latest lease truth from the control-plane record repository instead of inferring it from sandbox lifecycle rows alone
3. Validation gates:
   - contract tests for lease schema and append-only publication rules
   - unit tests for control-plane publication and sandbox reconciliation mapping
   - integration tests proving sandbox create, renewal, reconciliation, and cleanup write lease records

## Rollback Plan
1. Rollback trigger: the append-only lease publication shape blocks valid renewal or cleanup flows and a narrower truthful lease surface is required.
2. Rollback steps:
   - remove `publication_timestamp` from `LeaseRecord`
   - revert lease repository/publication methods and sandbox lease publication hooks
   - revert the packet docs and authority snapshot that describe live lease publication
3. Data/state recovery notes: existing lease rows in `.orket/durable/db/control_plane_records.sqlite3` may be left in place as superseded historical records; rollback does not require destructive database cleanup.

## Versioning Decision
- Version bump type: patch
- Effective version/date: next non-docs release after 2026-03-23
- Downstream impact: direct `LeaseRecord` constructors and any future control-plane repository implementations must carry `publication_timestamp` and preserve append-only lease history.
