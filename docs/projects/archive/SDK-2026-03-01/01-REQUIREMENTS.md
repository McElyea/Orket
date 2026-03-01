# Extension SDK v0 Requirements

Last updated: 2026-02-28

## Objective

Ship a minimal public SDK that makes one thing easy: build an extension workload that runs deterministically under Orket with explicit declared capabilities.

The SDK is workload-agnostic. It does not encode game-specific logic. Workload-specific decisions (TextMystery gameplay, Meta Breaker rules) live in their respective projects.

## Definitions

- **Extension**: Installable package that declares manifest metadata and workload entrypoints.
- **Workload**: Callable unit executed by Orket runtime via SDK contract.
- **Capability**: Runtime-provided dependency declared in manifest and resolved by registry.
- **Artifact**: Deterministic output file produced by workload execution.
- **Issue**: Structured diagnostic record reported by manifest validation or workload execution.

---

## SDK Module Contracts

### `orket_extension_sdk.manifest`

Models:
- `Manifest`
  - `extension_id: str`
  - `version: str`
  - `description: str`
  - `entrypoints: dict[str, list[str]]` (v0 key: `workloads`)
  - `requires_capabilities: list[str]`
  - `config_schema: dict | str | None` (optional)

Functions:
- `load_manifest(path) -> Manifest`
- `validate_manifest(manifest) -> list[Issue]`

Format: YAML primary, JSON accepted.

### `orket_extension_sdk.capabilities`

Types:
- `CapabilityId` -- string type alias
- `CapabilityProvider` protocol:
  - `provides() -> list[CapabilityId]`
  - `get(capability_id) -> object`
- `CapabilityRegistry` -- merges providers, resolves requirements

Capability interfaces (interface-only, no concrete SDK implementation):
- `AudioInput`
- `AudioOutput`
- `Console`
- `Clock`
- `KVStore` (namespaced, versioned operations)

### `orket_extension_sdk.workload`

Types:
- `WorkloadContext`
  - `capabilities` -- resolved capability registry
  - `run_id` -- unique run identifier
  - `seed` -- deterministic seed
  - `workspace_dir` -- confined output directory
  - `logger` -- structured logger
  - `artifacts` -- namespaced artifact writer
  - `trace` -- `trace.emit(event_type, payload)` observability seam
- `Workload` protocol:
  - `run(ctx: WorkloadContext, input: dict) -> WorkloadResult`

### `orket_extension_sdk.result`

Models:
- `WorkloadResult`
  - `status: "ok" | "stop" | "error"`
  - `output: dict`
  - `artifacts: list[ArtifactRef]`
  - `issues: list[Issue]`
- `ArtifactRef` -- identifies written artifacts with digest metadata
- `Issue` -- `code`, `message`, `stage`, `location`, `details`

### `orket_extension_sdk.testing`

Helpers:
- `FakeCapabilities` -- in-memory console/audio stubs
- `DeterminismHarness` -- N-run comparison using output + artifact digests
- `GoldenArtifact` -- snapshot assertion helper

---

## Determinism Requirements

1. Same workload input + same seed + same replay transcript must produce the same `WorkloadResult.output` and artifact digest set.
2. Timestamp/path noise must be normalized in determinism comparison.
3. Artifact writes must be confined to approved namespaces under workspace.

## Security Requirements

1. Missing required capabilities fail closed before execution.
2. Artifact path traversal or out-of-namespace writes are blocked.
3. Workloads cannot instantiate IO providers directly -- must go through `ctx.capabilities`.

## Acceptance Criteria

1. SDK package exposes only the v0 modules listed above.
2. Runtime can discover and validate extension manifests (YAML primary, JSON accepted).
3. Runtime can execute SDK workloads through `run(ctx, input)`.
4. Missing required capabilities fail closed before execution.
5. Demo extension executes and emits expected artifacts.
6. Determinism harness can verify replay stability.
7. Legacy extension path remains operational during migration period.
