# Package-Owned Runtime Contract Assets

## Summary
- Change title: Ship runtime defaults independently of the working directory.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `CORE_RUNTIME_STABILITY_REQUIREMENTS.md`,
  `CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md`, `RUNTIME_INVARIANTS.md`,
  `RUN_EVIDENCE_GRAPH_V1.md` and `TOOL_CONTRACT_TEMPLATE.md` under `docs/specs/`.

## Delta
- Opening behavior: a fresh wheel's card flows read `core/artifacts/` and
  `core/policies/` in CWD. Installed tests outside the checkout fail before card
  execution. Unrelated files in CWD can also become implicit policy inputs.
- Required behavior: the nine canonical files move, with unchanged bytes, from
  repository `core/{artifacts,policies,tools}/` to
  `orket/runtime/config/assets/{artifacts,policies,tools}/`. Package metadata
  includes them; `orket.runtime.config.contract_assets` owns shared locations.
  Contract and budget loaders use those installed defaults when a path is omitted.
  Orchestration uses the same prompt-budget default.
- The next installed attempt exposes a further dependency: runtime invariant
  snapshot collection reads the repository's Markdown contract. That contract
  becomes a tenth package asset under `assets/contracts/`; the old spec path is
  a documentation index, not a second contract copy. The same parser and startup
  drift gate continue to validate it. Explicit document paths remain supported.
  The INV-004 registry reference changes to the packaged registry location; new
  snapshots report their actual source path. Historical snapshots are unchanged.
- Explicit path arguments retain their existing meaning. A caller-supplied bad
  path fails; it never silently selects the packaged policy. Old CWD paths are
  neither implicit overrides nor compatibility copies. Existing retained
  snapshots and historical proof reports are not rewritten.
- Reason: installed execution must carry its required authoritative defaults,
  rather than depend on a hidden checkout or accidental CWD contents.

## Migration Plan
1. Compatibility: loader call signatures and explicit path semantics remain;
   default-location constants are owned by the new canonical config module.
   Repository callers and active specifications use that authority.
2. Steps: move the sole source copies, include package data, update default
   consumers and active references, then rebuild/install isolated wheels.
3. Gates: preserve raw bytes; exercise empty and impostor-containing foreign
   working directories, explicit valid/invalid overrides, actual installed card
   flows and live provider execution. Structural package inspection alone does
   not prove runtime acceptance. SR-07 remains open until its full gate passes.

## Rollback Plan
1. Trigger: changed contract contents, incomplete distribution, or incorrect
   explicit-override selection.
2. Steps: repair or restore the last verified package resource set and retain
   the failing installed proof. Do not substitute CWD discovery for authority.
3. Recovery: no database migration, schema-version change or historical evidence
   rewrite is involved. No production state is migrated by these proof runs.

## Versioning Decision
- No release, commit or version bump is performed in this checkpoint.
- Effective date: 2026-09-12; schema versions and validation rules are retained.
  Data-file bytes remain unchanged; the invariant contract's registry path moves.
- Downstream callers that intentionally used CWD defaults must supply explicit
  paths. Callers importing default locations use the canonical config module.
