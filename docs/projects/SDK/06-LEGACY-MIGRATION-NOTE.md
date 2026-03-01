# Legacy Extension Migration Note

Last updated: 2026-02-28

## Scope

This note covers migration from legacy extension authoring (`orket_extension.json` + `RunPlan`) to SDK v0 (`extension.yaml` + `run(ctx, input) -> WorkloadResult`).

## Public Seam Reminder

The public extension seam is:

`Workload.run(ctx, input) -> WorkloadResult`

`TurnResult` remains internal-only and is not a supported extension contract surface.

## Legacy to SDK Mapping

1. Manifest:
   - Legacy: `orket_extension.json`
   - SDK v0: `extension.yaml` (JSON accepted for compatibility)
2. Entrypoint:
   - Legacy: module + `register_callable` + workload class registration
   - SDK v0: `workloads[].entrypoint` (`module:symbol`)
3. Execution:
   - Legacy: `compile(input) -> RunPlan`, validators, summarize hooks
   - SDK v0: `run(ctx, input) -> WorkloadResult`
4. Artifacts:
   - Legacy: runtime artifact handling through plan execution path
   - SDK v0: workload declares `ArtifactRef` with digest for each output file
5. Dependencies:
   - Legacy: extension-owned provider instantiation
   - SDK v0: explicit capability preflight + `ctx.capabilities`

## Migration Checklist

1. Replace legacy manifest with `extension.yaml`.
2. Move workload logic into a `run(ctx, input)` entrypoint.
3. Emit `WorkloadResult` with explicit `artifacts` + digest metadata.
4. Remove references to runtime internals (`TurnResult`, private orchestration types).
5. Add deterministic tests for same-seed output and artifact digest stability.
6. Validate fail-closed behavior for missing required capabilities.

## Deprecation Readiness Criteria

Legacy path deprecation can begin when:

1. SDK v0 covers public extension scenarios.
2. Mixed-catalog execution (legacy + SDK) is regression-tested.
3. Author guide and migration docs are published and synchronized.
4. Runtime hardening gates (artifact confinement + digest checks) are enforced.
5. A removal notice window and target release are announced.
