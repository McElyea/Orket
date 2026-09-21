# Explicit Agent and epic calendar observations

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.52 candidate, 2026-09-20.
- Durable contract: `docs/specs/REMAINING_RUNTIME_INPUTS.md`.

## Delta and migration
Agent dialect selection previously read operator patterns after role loading;
construction now captures the model name and resolved family before those reads.
Pass `environment` explicitly to override ambient configuration, including with an
empty mapping. Construct a new Agent to adopt a changed model/dialect configuration.

Call `ModelFamilyRegistry.from_environment(mapping)` for environment decoding.
`from_config(None)` now means built-in defaults and performs no environment read.
Malformed operator JSON raises a bounded error instead of silently defaulting.
Supported structured pattern normalization is unchanged.

Agent journal publication consumes a timestamp captured from the selected clock
after the tool outcome, or the caller timestamp captured at run entry. The private
journal builder requires `publication_timestamp`. Failed clock observation can
leave a completed effect without a returned journal record; no success is invented.
Direct-tool gate and journal-authority requirements remain in force.

Epic setup captures one local calendar observation through `RuntimeInputService`
and an immutable baseline. Custom `EpicRunSetup` construction supplies
`calendar_sprint`; direct orchestrator construction can supply `eos_calendar`.
Existing stored card values and recovery authority are not rewritten. Newly
created cards in a later setup entry can use that entry's new sprint observation.

## Verification and rollback
Retain actual held role/asset reads, real file effects with journal records, real
SQLite card creation, negative clock/JSON controls, published default parity and
affected source/installed callers. Controlled providers do not prove inference.
Rollback callers and these input contracts together while preserving existing
card, session, outcome and journal evidence. No compatibility retry is added.

## Versioning decision
- Patch remediation checkpoint with explicit breaking input-boundary migrations.
- Remaining D input inventory, adapter enforcement, async safety, E/CAP and lane acceptance remain active.
