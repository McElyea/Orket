# Captured local prompt policy and registry observation

## Summary
- Change title: Application-owned prompt preparation over captured inputs.
- Owner: Orket Core.
- Date: 2026-09-17.
- Affected contracts: Local provider construction, local prompting policy, registry provenance and worker lifetime.

## Delta
- Current behavior: The provider adapter constructs prompt policy internally. The policy reads ambient environment, retains borrowed nested request values across an await, caches a mutable parsed registry globally, hashes a second file read, and abandons its read worker on caller cancellation.
- Proposed behavior: Application composition supplies the policy port. A service captures environment at construction and caller messages/context before its first await. A read-only storage worker captures registry bytes once; application validates those exact bytes and binds their digest. Cancellation retains the worker until it settles. Each request owns its parsed registry; no shared mutable cache participates. Returned policy values are immutable, and transport/telemetry exports are detached values.
- Why this break is required now: Four controlled adverse cases on unchanged 0.6.11 reproduced input drift, misleading registry provenance and escaped worker lifetime. Adapters must execute supplied authority without importing application policy.

## Migration Plan
1. Compatibility window: No forwarding shim. Replace direct construction with `orket.application.services.local_model_factory.create_local_model_provider`; raw `LocalModelProvider` requires an explicit prompt-policy port.
2. Migration steps: Move prompt-policy orchestration into application; move the shared policy result/port into core; pass captured settings through the application factory; migrate repository runtime, tooling and test callers. Move the SDK model owner from `orket.capabilities.sdk_llm_provider` to `orket.application.services.sdk_llm_provider` without a shim. The packaged registry asset and its schema remain at their existing paths. Preserve profile matching, fallback, strict rejection, compaction, sampling caps and exact stop-token bytes.
3. Validation gates: Adverse controls, request/registry isolation and cancellation proof, affected behavior tests, source/package parity, installed native envelopes, actual llama.cpp flow, dependency delta and authority checks. Completion evidence is recorded in the canonical remediation plan; this proposal alone supplies no acceptance proof.

## Rollback Plan
1. Rollback trigger: Required provider semantics or packaging cannot be preserved.
2. Rollback steps: Revert the complete migration together; retain failed and successful proof artifacts.
3. Data/state recovery notes: This is read-only registry preparation. No runtime database migration or provider lifecycle restart is authorized by this change.

## Versioning Decision
- Version bump type: Patch checkpoint destined for main; matching local annotated tag after verification.
- Effective version/date: 0.6.12 local checkpoint, 2026-09-17.
- Downstream impact: Internal direct provider constructors must use application composition or supply the core port. Policy collections become immutable; use detached transport/telemetry exports for mutable payloads. No claim of OS containment, full replay capture, whole-core purity or complete C/D conformance. Legacy profile file loaders and other remaining boundaries stay tracked in the active plan.
