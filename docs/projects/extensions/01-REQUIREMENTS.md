# Extensions v1 Requirements

## Scope
Define a single public extension system for Orket that supports external installable workloads, deterministic execution, and fail-closed governance.

## Definitions
- Engine: Core Orket runtime.
- Governance: Deterministic preflight + validation + provenance + fail-closed behavior.
- Extension: Installable package that integrates with Orket.
- Ork: User-facing name for an Extension.
- Workload: Executable capability registered by an Extension.

## Core Requirements

### R0 (Public Surface)
R0: The only public extension point is ExtensionManager + Workload contract.
DecisionNodeRegistry is internal-only and not documented as a plugin surface.

### R1 (Single System)
- Orket must expose one extension model to users and extension authors.
- DecisionNodeRegistry may be used internally by engine/runtime code only.
- Public docs, CLI, and examples must reference ExtensionManager + Workload only.

### R2 (Third-Party Install + Run UX)
- A third-party extension (mystery_v1) can be installed from a separate repo and run with:

```bash
orket extensions list

orket run mystery_v1 --seed 123
```

- This must work without any direct node wiring by extension authors.

### R3 (Extension Contract)
- An Extension must provide:
- `extension_id` (stable string)
- `extension_version` (semver-compatible string)
- `register(registry)` entrypoint
- `register(registry)` must register one or more Workloads.

### R4 (Workload Contract)
- A Workload must provide:
- `workload_id`
- `workload_version`
- `compile(input_config) -> RunPlan`
- `validators() -> list`
- `summarize(run_artifacts) -> summary object`
- `required_materials()`
- A Workload must not:
- invoke model execution directly
- bypass arbiter
- write outside artifact root

### R5 (Engine Responsibilities)
- Engine must:
- discover Extensions via entry point registry
- load extension metadata and compatibility constraints
- enforce governance before execution
- execute RunPlan deterministically
- produce governed artifacts only under artifact root
- capture provenance
- fail closed on material mismatch

### R6 (Reliable Mode Default)
- Reliable Mode is default.
- Reliable Mode must:
- require preflight material validation
- require clean git state when configured
- require deterministic artifact writes
- enforce post-run validation
- emit `provenance.json`

### R7 (Isolation + Capability Boundaries)
- Extensions must not:
- import private engine modules
- mutate engine global state
- depend on filesystem paths outside artifact root
- Engine/runtime must enforce these constraints with technical controls (not docs-only policy).

### R8 (Determinism + Reproducibility)
- `RunPlan` must be canonicalized and hashable (`plan_hash`).
- Equivalent inputs must produce identical `plan_hash`.
- Artifact manifest must include deterministic file hash set.
- Re-run with same inputs and materials must produce identical governed outputs or fail closed.

### R9 (Versioning + Compatibility)
- Extension manifest must declare:
- `extension_api_version`
- compatible runtime range (min/max or semver range)
- Runtime must reject incompatible extensions with deterministic error codes.

### R10 (Initial Target Extension)
- The Mystery Game must be implemented as an external Extension (Ork).
- It must:
- register workload `mystery_v1`
- use precomputed deterministic graph
- use truth-or-silence model policy
- produce governed artifacts

## Acceptance Criteria
- Third-party `mystery_v1` extension can be installed from another repo and listed via `orket extensions list`.
- `orket run mystery_v1 --seed 123` executes through ExtensionManager path only.
- No external extension requires `DecisionNodeRegistry` APIs.
- Reliable Mode governance checks fail closed with deterministic codes.
- `provenance.json` and artifact manifest are emitted for successful runs.
