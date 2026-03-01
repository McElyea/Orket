# Extension SDK v0 Migration and Compatibility

## Objective

Define migration policy and compatibility boundaries for adopting the SDK v0 workload seam while keeping current extension users unblocked.

Status note:
- Gameplay implementation can pause; migration/compat planning continues against locked Layer-0 seams.
- Term lock: `deterministic runtime policy` means hint + disambiguation behavior.

## Compatibility Policy

### Public compatibility promise (v0)

Within the same major version:
1. Manifest schema contract (`Manifest`) remains stable.
2. Workload return contract (`WorkloadResult`) remains stable.
3. Capability declaration and resolution contract remains stable at the public interface level.
4. Workload observability entrypoint (`ctx.trace.emit(...)`) remains stable at the public interface level.

### Explicit non-promise

The following are internal and may change without extension API guarantees:
1. `TurnResult` and engine orchestration internals.
2. Internal trace storage schema and execution pipeline internals.
3. Non-public runtime adapter implementation details.
4. Demo-specific deterministic runtime-policy phrasing details.

## Migration Strategy

Use dual-path bridging.

1. Keep legacy extension runtime path operational.
2. Add SDK v0 path in parallel.
3. Allow mixed extension catalogs during transition.
4. Move docs and examples to SDK v0 as canonical authoring path.
5. Treat TextMystery gameplay-kernel behavior as a proving ground, not a required public SDK contract surface.

## Manifest Format Policy

1. `extension.yaml` is the normative author-facing format.
2. JSON manifests remain accepted for compatibility.
3. Parse/validation errors must report stable issue codes and field locations.

## Runtime Behavior During Transition

1. Runtime detects contract style and routes execution to the appropriate path.
2. Capability preflight is fail-closed for SDK v0 runs.
3. Artifact write confinement rules apply uniformly.
4. Deterministic artifact manifest and provenance behavior remains mandatory.
5. Runtime policy quality checks (hint/disambiguation loops) are test-gated for demo stability, but do not expand public SDK API guarantees.

## Deprecation Criteria for Legacy Path

Legacy path deprecation should begin only after all criteria are met:

1. SDK v0 can cover current public extension use cases.
2. Public reference extension and docs are stable.
3. Migration guide exists with examples and known limitations.
4. Conformance tests cover both paths and no critical regressions remain.
5. Notice period and target removal release are published.
6. SDK docs and migration docs are synchronized with Layer-0 lock and no longer contain conflicting public seam guidance.

## Rollout Gates

1. Contract gate:
   - SDK models and validation tests green.
2. Runtime gate:
   - v0 and legacy paths both pass integration suites.
3. Determinism gate:
   - repeat-run digest stability checks pass.
4. Docs gate:
   - public docs show only SDK seam as recommended path.
5. Policy gate:
   - deterministic runtime-policy checks pass for repeat suppression and disambiguation command flow.

## Risks and Mitigations

1. Risk: Extension authors bind to private runtime internals.
   - Mitigation: clear policy and lint/conformance checks for forbidden imports.
2. Risk: Migration uncertainty for legacy authors.
   - Mitigation: dual-path bridge plus explicit migration guide and timeline.
3. Risk: Cross-environment output drift.
   - Mitigation: determinism harness, transcript replay, normalized comparison.
4. Risk: Capability mismatch at runtime.
   - Mitigation: fail-closed preflight with actionable issue diagnostics.
5. Risk: Dual-track work (game + SDK) causes drift in migration messaging.
   - Mitigation: maintain Layer-0 lock as source of truth and run periodic doc sync checkpoints.

## Required Test Coverage for Migration

1. Mixed registry execution:
   - one legacy extension and one SDK v0 extension in same catalog.
2. Capability preflight failures:
   - deterministic error behavior and stable issue payloads.
3. Workload result contract checks:
   - invalid status/output/artifacts handling.
4. Artifact namespace safety:
   - path escape attempts blocked.
5. Replay determinism:
   - same seed + same transcript yields matching output and digests.
6. Runtime policy conformance:
   - repeated-question nudges do not loop indefinitely
   - disambiguation prompt handles `back/help/quit` paths deterministically
