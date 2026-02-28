# Extension SDK v0 Requirements

## Objective

Ship a minimal public SDK that makes one thing easy:
- Build an extension workload that runs deterministically under Orket with explicit declared capabilities.

Current planning mode:
- Gameplay tuning may pause temporarily.
- SDK seam decisions continue and must stay compatible with the Layer-0 lock in `docs/projects/SDK/00-IMPLEMENTATION-PLAN-SDK-LAYER-0.md`.
- Term lock: `deterministic runtime policy` means hint + disambiguation behavior.

## Definitions

- Extension: Installable package that declares manifest metadata and workload entrypoints.
- Workload: Callable unit executed by Orket runtime via SDK contract.
- Capability: Runtime-provided dependency declared in manifest and resolved by registry.
- Artifact: Deterministic output file produced by workload execution.
- Issue: Structured diagnostic record reported by manifest validation or workload execution.

## v0 SDK Surface (Minimal)

v0 must include only these modules.

### `orket_extension_sdk.manifest`

Required model:
- `Manifest`
  - `extension_id: str`
  - `version: str`
  - `description: str`
  - `entrypoints: dict[str, list[str]]` (v0 uses `workloads`)
  - `requires_capabilities: list[str]`
  - `config_schema: dict | str | None` (optional object or pointer)

Required functions:
- `load_manifest(path) -> Manifest`
- `validate_manifest(manifest) -> list[Issue]`

### `orket_extension_sdk.capabilities`

Required types and interfaces:
- `CapabilityId` string type alias.
- `CapabilityProvider`:
  - `provides() -> list[CapabilityId]`
  - `get(capability_id) -> object`

Required capability interfaces (interface-only, no concrete SDK IO implementation):
- `AudioInput`
- `AudioOutput`
- `Console`
- `Clock`
- `KVStore` (namespaced and versioned operations)

Required helper:
- `CapabilityRegistry` that merges providers and resolves capability requirements.

### `orket_extension_sdk.workload`

Required types:
- `WorkloadContext`
  - `capabilities`
  - `run_id`
  - `seed`
  - `workspace_dir`
  - structured `logger`
  - namespaced `artifacts` writer
  - `trace.emit(event_type, payload)` observability seam

- `Workload` protocol:
  - `run(ctx: WorkloadContext, input: dict) -> WorkloadResult`

### `orket_extension_sdk.result`

Required models:
- `WorkloadResult`
  - `status: "ok" | "stop" | "error"`
  - `output: dict`
  - `artifacts: list[ArtifactRef]`
  - `issues: list[Issue]`

- `ArtifactRef`
  - identifies written artifacts and digest metadata

- `Issue`
  - `code`, `message`, `stage`, `location`, `details`

### `orket_extension_sdk.testing`

Required helpers:
- `FakeCapabilities` (in-memory console/audio stubs)
- `DeterminismHarness` (N-run comparison using output + artifact digests)
- `GoldenArtifact` (snapshot assertion helper)

## Public API and Interface Locks

1. Public seam (v0): `Workload.run(ctx, input) -> WorkloadResult`
2. Dependencies are injected via runtime capability registry/providers.
3. Runtime internal orchestration types stay private; `TurnResult` is not a public SDK contract.
4. Observability seam for extensions is limited to `ctx.trace.emit(...)` plus artifacts.
5. Companion and UX policy rules are deterministic and replay-safe when included in demo runtime behavior.

## Gameplay Kernel Alignment Requirements (Layer-0 Demo Constraint)

These are requirements for the first public demo workload path (TextMystery-driven) so SDK extraction does not drift away from practical gameplay quality.

1. Typed fact payloads in demo gameplay include explicit `kind`.
2. Discovery keys use stable namespaced format:
   - `disc:fact:*`
   - `disc:place:*`
   - `disc:object:*`
   - `disc:npc:*`
3. Deterministic runtime policy must be non-repeating:
   - suppress repeated suggestions
   - avoid suggesting recently asked prompts
   - support hint target cooldown markers (for example `disc:hint:*`)
4. Hint policy should be actor-aware for actionable suggestions:
   - avoid nudges that the current NPC cannot answer
   - allow deterministic cross-suspect suggestion when appropriate
5. Disambiguation flow must support control commands (`back`, `help`, `quit`) and not trap user input loops.

## First Public Extension Requirement

The first public reference extension must be:
- `orket-extension-mystery-game-demo` (external repository)

It must prove:
1. Manifest discovery and entrypoint loading.
2. Capability requirement declaration (`console`, `audio_output`; `audio_input` optional later).
3. Artifact writing under run workspace.
4. Deterministic structured outcome behavior.

Expected artifacts:
- `artifacts/transcript.jsonl`
- `artifacts/session_summary.json`
- `artifacts/pattern_used.json`

## Determinism Requirements

1. Same workload input + same seed + same replay transcript must produce the same:
   - `WorkloadResult.output`
   - artifact digest set
2. Timestamp/path noise must be normalized in determinism comparison.
3. Artifact writes must be confined to approved artifact namespaces under workspace.

## Acceptance Criteria

1. SDK package exposes only the minimal v0 modules and required contracts in this document.
2. Runtime can discover and validate extension manifests with YAML primary and JSON support.
3. Runtime can execute SDK workloads through `run(ctx, input)`.
4. Missing required capabilities fail closed before execution.
5. Demo extension executes and emits expected artifacts.
6. Determinism harness can verify replay stability.
7. Legacy extension path remains operational during migration period.
8. Demo hint/disambiguation behavior remains deterministic and does not regress into repeated-loop coaching.
