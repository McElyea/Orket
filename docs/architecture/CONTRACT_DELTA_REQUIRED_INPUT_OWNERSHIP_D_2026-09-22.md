# Shared required-read observations and Packet-1 construction inputs

## Summary
- Change title: Explicit required-read observations and stable run-level intent.
- Owner: Orket Core.
- Date: 2026-09-22.
- Last updated: 2026-09-23.
- Affected contracts: `PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`, existing
  workspace constraints in `PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`, and
  `TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` and `SETTINGS_INPUT_OWNERSHIP.md`.

## Delta
- Before v0.6.101: upstream context, response validation and protocol preflight
  perform synchronous metadata work on async paths. Validation and corrective
  rendering can reobserve the same declarations within one response attempt.
  Run-level Packet-1 intended provider/profile reads ambient environment at start
  and finalization, despite an existing construction snapshot.
- Required behavior: use one explicit application observation boundary with the
  existing PathResolver policy and native owner; capture only consumed values.
  Pure validation and corrective rendering share the attempt's observation, while
  retry and dispatch observations are fresh. Packet-1 uses the existing runtime
  construction environment and existing provider/profile precedence.
- Preserve distinct governed preload, legacy regular-file, exists-only context
  and submitted-path semantics. Preserve per-tool binding/policy/compatibility/
  workspace/gate/skill/approval order; whole-turn path batching is prohibited.
- Bind successful validation and preflight to the captured proposed calls used by
  execution. Caller mutation during metadata work cannot substitute commands after
  admission. Dispatch publishes its captured turn before execution awaits, including
  raised paths; existing result publication authority remains explicit. Capture
  named production context inputs and borrow unknown extension values by identity.
- Preserve Packet-1 actual telemetry precedence, default/missing tokens, merging,
  projection and physical-summary schemas. Fallback profile is selected only after
  fallback telemetry; start without telemetry still has profile `default`.
- Native automatic pipeline capture observes its consumed root, environment and
  settings only. Explicitly unobserved preferences use `None` and refuse access or
  binding with `E_RUNTIME_PREFERENCES_NOT_CAPTURED`. Supplied full inputs, default
  synchronous capture and existing async factory/engine/API/CLI capture retain
  full preference behavior and native migration refusals. No second input owner,
  lock retry, serialized restart or fabricated empty preference snapshot is added.
- Why now: matched source/.100 wheel controls reproduce three metadata stalls and
  ambient Packet-1 drift. One original healthy Packet-1 failure was a fixture
  expectation error; phase-aware controls retain one healthy pass and one drift
  failure per cell. Exact separate observations are retained in the plan.
- Limits: no atomic filesystem snapshot, forced thread termination, hard native
  deadline, new read capability, complete executor/custom-consumer capture or
  provider admission.

## Migration Plan
1. Target v0.6.101; the canonical architectural-truth plan records acceptance status.
2. Move async callers to owned observations and migrate validation/corrective
   signatures to explicit attempt inputs. No compatibility shim or sync fallback.
3. Supply runtime environment before pipeline construction. Native construction
   without a snapshot captures through the existing construction authority and
   excludes unused preferences. Native embeddings needing preferences explicitly
   provide full inputs; existing async factory callers retain full capture.
4. Preserve accepted BT behavior and every prior assertion unless an explicit
   signature/fixture migration requires a documented mechanical adaptation.
   Custom middleware must publish through borrowed output containers; replacing or
   deleting captured dispatch-context entries does not update the caller's mapping.
5. Prove healthy/negative path parity, all reached native metadata sites, repeat
   cancellation/timeout/late failure, captured values, no-later-stage admission,
   corrective/retry consistency, real dispatch ordering and physical Packet-1
   summary/SQLite parity. Freeze candidate bytes for source and installed Windows
   3.11/3.12, complete package parity, canonical C and quality checks. Retain the
   exact Linux clock blocker and wider D/E/CAP claim ceilings independently.

## Rollback Plan
1. Trigger: changed path admission/order, lost provenance, altered valid output or
   escaped native work.
2. Repair forward through the same policy and resource owners; retain failed and
   passing evidence and do not restore hidden ambient reads or unowned work.
3. No ledger resealing, state deletion or schema migration is required.

## Versioning Decision
- Version bump type: patch; scoped architectural remediation.
- Target version/date: 0.6.101 / 2026-09-23.
- `compatibility_status`: `breaking`.
- `affected_audience`: `all`.
- `migration_requirement`: `required`.
- Downstream impact: explicit validation inputs, async metadata ownership,
  per-attempt observations and construction-bound Packet-1 intent.
