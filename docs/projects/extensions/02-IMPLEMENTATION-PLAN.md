# Extensions v1 Implementation Plan

## Objective
Deliver one public extension system (`ExtensionManager + Workload contract`) while preserving internal runtime stability and avoiding dual plugin surfaces.

## Execution Strategy
1. Build a public Extension runtime layer first.
2. Bridge internally to existing runtime seams where needed.
3. Deprecate legacy public-facing node overrides after extension parity is achieved.

## Phase 1: Contract and Runtime Skeleton

### Deliverables
- `ExtensionManifest` schema with:
- `extension_id`, `extension_version`, `extension_api_version`, compatibility range
- entrypoint metadata for `register(registry)`
- `Workload` protocol and `RunPlan` model with canonical serialization support
- `ExtensionManager` with:
- discovery (entry points + explicit repo install metadata)
- install/list/load lifecycle
- workload registry
- CLI commands:
- `orket extensions list`
- `orket run <workload_id> [args]`

### Implementation Notes
- Keep `DecisionNodeRegistry` internal; no extension-facing dependency.
- Add thin adapter where engine execution path requires current internals.

### Exit Criteria
- Runtime can load at least one local extension package.
- `orket extensions list` returns installed extensions/workloads from ExtensionManager.
- Workload invocation path enters engine via ExtensionManager only.

## Phase 2: Governance and Determinism Hardening

### Deliverables
- Reliable Mode default enforcement in extension run path.
- Preflight material validation + optional clean git requirement.
- Canonical `RunPlan` hashing (`plan_hash`) and deterministic artifact manifest hashing.
- Post-run validator execution and fail-closed status model.
- Provenance emission (`provenance.json`) with:
- extension/workload/version
- input config digest
- plan hash
- material and artifact hashes
- Deterministic error taxonomy for:
- install/discovery failures
- compatibility failures
- governance/preflight failures
- execution failures
- postflight validation failures

### Exit Criteria
- Same inputs/materials produce identical `plan_hash`.
- Artifacts and provenance pass deterministic replay checks.
- Governance failures return stable error codes and block output publication.

## Phase 3: Third-Party Extension Path (mystery_v1)

### Deliverables
- Third-party install flow from separate repo for `mystery_v1`.
- Reference extension package implementing:
- workload `mystery_v1`
- deterministic graph compilation
- truth-or-silence policy
- governed artifact outputs
- End-to-end CLI UX:
- `orket extensions list`
- `orket run mystery_v1 --seed 123`

### Exit Criteria
- `mystery_v1` runs with no direct node wiring by extension authors.
- Extension output is fully governed and reproducible under Reliable Mode.

## Phase 4: Public Surface Consolidation

### Deliverables
- Public docs updated to extension-only model.
- Explicit statement that `DecisionNodeRegistry` is internal-only.
- Deprecation notices for legacy public node override mechanisms.
- Conformance tests for extension contract, governance, and replay.

### Exit Criteria
- Docs and examples contain a single extension model.
- CI includes extension conformance gate.
- No published plugin guidance references direct decision-node customization.

## Work Breakdown (Initial)
1. Create schema/models: manifest, workload, runplan, provenance.
2. Implement `ExtensionManager` discovery/install/list/load.
3. Add CLI commands for list/run.
4. Integrate Reliable Mode checks in workload execution path.
5. Add deterministic hashing and replay assertions.
6. Build and validate `mystery_v1` reference extension from separate repo.
7. Update docs and deprecate legacy public plugin guidance.

## Risks and Mitigations
- Risk: Dual-surface confusion persists.
- Mitigation: Hard doc rule and CLI/API routing only through ExtensionManager.
- Risk: Determinism breaks across environments.
- Mitigation: Canonical serialization, pinned material validation, replay tests in CI.
- Risk: Legacy internals leak into extension authoring.
- Mitigation: Lint/contract checks that reject extension references to internal runtime modules.
