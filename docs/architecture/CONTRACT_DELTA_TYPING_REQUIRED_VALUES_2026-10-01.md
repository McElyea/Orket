# Required values exposed by canonical typing

## Summary
- Change title: Explicit API, epic-success and controller-schema admission.
- Owner: Orket Core.
- Date: 2026-10-01 (America/Denver).
- Affected contracts: `docs/specs/API_RUNTIME_LIFECYCLE.md`,
  `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and
  `CONTRACT_DELTA_CONTROLLER_SCHEMA_CD_2026-09-19.md`.

## Delta
- Previous behavior: Missing API authentication failed through attribute access;
  missing interaction managers could reach command construction. A missing epic
  success snapshot failed through subscripting. Non-object/non-boolean JSON schema
  roots reached the external validator with incidental failure behavior.
- Resulting behavior: API selection raises explicit `RuntimeError` before startup
  or interaction dispatch when its required owner is absent. Outer preparation
  still closes acquired resources. Epic success publication refuses an absent
  snapshot with `E_EPIC_PUBLICATION_SUCCESS_SNAPSHOT_REQUIRED` before success/event
  publication, preserving earlier phases. Controller schema validation rejects an
  invalid root with `controller.observability_schema_root_invalid`; object and
  boolean schema semantics remain owned by the existing JSON Schema validator.
- Why required now: Canonical annotations must describe actual admitted values.
  These boundaries need explicit refusal, rather than a cast masking absent state.
  Missing attempt references retain their existing authority-conflict outcome;
  null model scores retain the existing invalid-row count. Neither is a new
  recovery or fallback contract.

## Migration Plan
1. Compatibility window: Effective with this scoped checkpoint; no compatibility
   shim for invalid internal construction.
2. Internal embeddings provide API authentication and interaction owners, retain
   the accepted epic snapshot and supply an object or boolean schema root. Update
   code that depended on incidental exception types. Healthy public flows require
   no operator action. No persisted format or provider selection changes.
3. Validation: Native API lifespan/HTTP cleanup and refusal, retained epic
   publication, actual schema reads, missing-attempt authority and score-report
   controls; canonical Mypy and existing structural gates. Both Quality jobs keep
   the new API module alongside existing controls. Hosted execution remains ATG-09.

## Rollback Plan
1. Trigger: A demonstrated valid-input or cleanup regression.
2. Revert the affected code, tests and contract changes together; restore truthful
   typing failure if needed rather than suppressing the diagnostics.
3. Earlier durable effects remain retained. Inspect existing journal/authority
   records before retrying; no new rollback or state-repair procedure is promised.

## Versioning Decision
- Patch checkpoint: 0.6.123, effective 2026-10-01.
- Internal invalid-input exception/admission behavior changes; required migration
  is limited to embeddings relying on incomplete construction or invalid schemas.
- This does not close coverage, installed-platform, provider or hosted acceptance.
