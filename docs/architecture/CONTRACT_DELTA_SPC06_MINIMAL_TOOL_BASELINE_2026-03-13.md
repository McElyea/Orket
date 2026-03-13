# Contract Delta Proposal

## Summary
- Change title: SPC-06 minimal tool-baseline closeout narrowing
- Owner: Orket Core
- Date: 2026-03-13
- Affected contract(s): `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`, `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md`, `docs/specs/RUNTIME_INVARIANTS.md`

## Delta
- Current behavior: the active specs overclaim a richer baseline-tool registry contract (`input_schema`, `output_schema`, `error_schema`, `side_effect_class`, timeout, retry) and describe `tool_invocation_manifest.json` as a standalone emitted artifact even though the shipped closeout surface is a smaller registry plus normalized invocation-manifest evidence embedded in tool events and protocol receipts.
- Proposed behavior: the active specs narrow SPC-06 to the shipped minimal registry fields (`tool_name`, `ring`, `tool_contract_version`, `determinism_class`, `capability_profile`) and describe invocation-manifest evidence using the current embedded protocol surface.
- Why this break is required now: leaving the larger contract active creates false completion pressure and inaccurate operator expectations about what the shipped runtime actually validates and emits.

## Migration Plan
1. Compatibility window: immediate on merge; this is a source-of-truth narrowing to current shipped behavior.
2. Migration steps:
   - treat the minimal registry fields as the canonical SPC-06 closeout surface
   - keep richer tool metadata in governance/template scope until a later explicit scope expansion
   - use normalized invocation-manifest evidence from tool events and receipts as the operator-facing proof surface
3. Validation gates:
   - contract bootstrap tests for minimal registry validation
   - dispatcher/artifact integration tests for capability and invocation-manifest enforcement
   - docs hygiene check

## Rollback Plan
1. Rollback trigger: a new closeout decision explicitly expands SPC-06 to require richer registry metadata or standalone manifest artifact emission.
2. Rollback steps:
   - restore the broader active requirement text only with matching runtime implementation and proof
   - update the contract delta and closeout plan to reflect the widened target
3. Data/state recovery notes: no data migration is required because the change narrows docs to current emitted behavior.

## Versioning Decision
- Version bump type: none for this docs/test closeout delta by itself
- Effective version/date: 2026-03-13
- Downstream impact: operators should rely on minimal registry metadata plus embedded invocation-manifest evidence, not on richer registry fields or a standalone `tool_invocation_manifest.json` artifact for SPC-06 closeout.
