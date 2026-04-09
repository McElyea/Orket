# Extension Capability Authorization Implementation Plan

Last updated: 2026-04-08
Status: Active
Owner: Orket Core
Lane type: Extension capability authorization / active first-slice implementation lane

Requirements authority: `docs/projects/ExtensionCapabilityAuthorization/EXTENSION_CAPABILITY_AUTHORIZATION_REQUIREMENTS.md`
Durable planning contract: `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`

## Authority posture

This document is the canonical implementation authority for the active Extension Capability Authorization lane recorded in `docs/ROADMAP.md`.

The requirements document remains the live requirements authority for this lane.
The durable spec remains the frozen planning contract authority.

This lane is intentionally bounded to the first executable slice:
1. host-issued authorization identity
2. child-side revalidation across the subprocess boundary
3. runtime authorization enforcement for `model.generate`, `memory.query`, and `memory.write`

Future capability families remain deferred until this first slice closes truthfully.

## Source authorities

This plan is bounded by:
1. `docs/projects/ExtensionCapabilityAuthorization/EXTENSION_CAPABILITY_AUTHORIZATION_REQUIREMENTS.md`
2. `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`
3. `docs/specs/TOOL_EXECUTION_GATE_V1.md`
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
5. `docs/ROADMAP.md`
6. `docs/ARCHITECTURE.md`
7. `CURRENT_AUTHORITY.md`
8. `docs/architecture/event_taxonomy.md`
9. `orket/extensions/workload_executor.py`
10. `orket/extensions/sdk_workload_runner.py`
11. `orket/extensions/sdk_workload_subprocess.py`
12. `orket/extensions/workload_artifacts.py`
13. `orket/extensions/artifact_provenance.py`
14. `orket_extension_sdk/capabilities.py`
15. `tests/runtime/test_extension_manager.py`
16. `tests/runtime/test_extension_components.py`
17. `tests/core/test_runtime_event_logging.py`

## Purpose

Implement one host-owned authorization surface for SDK capability invocation that survives subprocess execution without drift, remains subordinate to host validation and tool-gate authority, and produces proof strong enough to support a truthful fail-closed runtime claim for the first slice.

## Current truthful starting point

1. `WorkloadExecutor.run_sdk_workload(...)` builds a parent capability registry, preflights missing providers, and currently fails only on `E_SDK_CAPABILITY_MISSING`.
2. `run_sdk_workload_in_subprocess(...)` serializes extension, workload, and runtime context data, but does not serialize a host-issued admitted capability decision.
3. `sdk_workload_subprocess.py` rebuilds a fresh capability registry in the child from request context.
4. `WorkloadArtifacts.build_sdk_capability_registry(...)` auto-registers default providers for `model.generate`, `memory.write`, `memory.query`, voice, and audio families when providers are absent.
5. `CapabilityRegistry.get()` and the typed helper methods enforce provider presence and type only; they do not encode declared, admitted, instantiated, or used authorization state.
6. Current provenance records declared `required_capabilities`, but not admitted, instantiated, or used capability sets.
7. `docs/architecture/event_taxonomy.md` does not yet define the required `sdk_capability_call_*` event family.
8. No canonical audit-artifact producer exists yet for schema `extension_capability_audit.v1`.

## Decision lock

The following remain frozen while this plan is active:
1. The canonical seam is `host_authorized_capability_registry_v1`.
2. Capability preflight remains admissibility checking only; it is not runtime authorization.
3. The parent must compute `admitted_capabilities` before subprocess execution.
4. The child must consume and revalidate a host-issued authorization envelope.
5. Child-side executable capability expansion beyond the admitted set must fail closed with `E_SDK_CAPABILITY_AUTHORIZATION_DRIFT`.
6. `declared_capabilities`, `admitted_capabilities`, `instantiated_capabilities`, and `used_capabilities` remain distinct first-class vocabulary.
7. Capability auto-registration may remain an implementation convenience, but it is non-authoritative.
8. `memory.query` and `memory.write` remain separate authorities.
9. `workspace.root` and `artifact.root` remain structural context authority, not ordinary invocation capabilities.
10. Engine-delegated `run_card(...)` paths stay in the Tool Gate Enforcement lane.
11. This implementation lane is currently limited to `model.generate`, `memory.query`, and `memory.write`.

## Non-goals

This first slice does not:
1. invent a broad new capability policy language
2. widen the lane to voice, TTS, audio, or turn-control families
3. claim OS-level sandboxing or Python-stdlib confinement from capability authorization alone
4. move runtime authority into extension code, manifest validation, or UI or API wrappers
5. reopen the governed turn-tool gate story or treat engine-delegated `run_card(...)` paths as part of this slice
6. claim full-SDK capability closure when only the first slice is implemented

## Same-change update targets

At minimum, lane execution must keep these surfaces aligned in the same change when their story changes:
1. `docs/ROADMAP.md`
2. `docs/projects/ExtensionCapabilityAuthorization/EXTENSION_CAPABILITY_AUTHORIZATION_REQUIREMENTS.md`
3. `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md` when the durable contract changes materially
4. `docs/specs/TOOL_EXECUTION_GATE_V1.md` when the cross-lane authority split changes materially
5. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md` when validation-to-runtime wording changes materially
6. `docs/architecture/event_taxonomy.md` when `sdk_capability_call_*` events land
7. `CURRENT_AUTHORITY.md` when the active authority story changes materially
8. `docs/API_FRONTEND_CONTRACT.md` only if API-visible request, response, or error behavior changes

## Workstream 0 - Host-issued authorization envelope

### Goal

Compute one admitted capability decision in the parent and make that exact decision survive subprocess execution without expansion drift.

### Tasks

1. Add one shared host authorization helper surface instead of duplicating parent and child policy logic in multiple modules.
2. Build `declared_capabilities`, `admitted_capabilities`, `authorization_basis`, `policy_version`, and `authorization_digest` before subprocess start.
3. Extend the subprocess request payload to carry the host-issued authorization envelope.
4. Rebuild the child registry and fail closed before workload code executes if the child-instantiated capability surface would expand executable authority beyond the admitted set.
5. Preserve distinct failure truth for `declared_invalid`, `denied`, `admitted_unavailable`, and `authorization_drift`.
6. The child may validate envelope identity against the instantiated capability surface, but it may not mint, recompute, or widen `admitted_capabilities` on its own.

### Exact code surfaces

1. `orket/extensions/workload_executor.py`
2. `orket/extensions/sdk_workload_runner.py`
3. `orket/extensions/sdk_workload_subprocess.py`
4. `orket/extensions/workload_artifacts.py`

### Exit criteria

1. The parent computes and serializes an admitted capability decision on every SDK workload run.
2. The child cannot execute with broader authority than the parent admitted.
3. Drift fails with `E_SDK_CAPABILITY_AUTHORIZATION_DRIFT` on the real subprocess path.
4. The authorization envelope identity is recorded in provenance and proof artifacts.
5. Child-side code does not silently recompute admission policy.

## Workstream 1 - Invocation enforcement for the first slice

### Goal

Make unauthorized capability use fail closed at invocation time even when provider objects exist.

### Tasks

1. Introduce one governed registry view or provider-wrapper seam that intercepts first-slice invocation surfaces instead of relying on provider absence.
2. Keep auto-registration non-authoritative: a provider may exist, but non-admitted capabilities must remain unusable at runtime.
3. Preserve separate authorization meaning for `memory.query` and `memory.write`.
4. Keep `workspace.root` and `artifact.root` available as host-issued structural context without treating them as proof of executable capability admission.
5. Freeze stable runtime results for undeclared use, declared-but-not-admitted use, admitted-but-unavailable provider, and authorization drift.

### Exact code surfaces

1. `orket_extension_sdk/capabilities.py`
2. `orket/extensions/workload_artifacts.py`
3. `orket/capabilities/sdk_llm_provider.py`
4. `orket/capabilities/sdk_memory_provider.py`
5. any new host-owned wrapper module introduced to avoid duplicating enforcement logic

### Exit criteria

1. `model.generate`, `memory.query`, and `memory.write` can be admitted independently.
2. Declared-but-not-admitted use blocks before side effects.
3. Undeclared use blocks even if a provider object is present in the child registry.
4. Admitted-but-unavailable provider failure remains distinct from authorization denial.
5. No first-slice access path through `CapabilityRegistry.get()` or the typed helper methods bypasses the governed authorization seam.

## Workstream 2 - Telemetry, provenance, and audit artifact

### Goal

Make first-slice authorization truth observable enough to prove closure.

### Tasks

1. Emit `sdk_capability_call_start`, `sdk_capability_call_blocked`, `sdk_capability_call_result`, and `sdk_capability_call_exception`.
2. Carry required fields: `extension_id`, `workload_id`, `run_id`, `capability_id`, `capability_family`, `authorization_basis`, `declared`, `admitted`, and `side_effect_observed`.
3. Record `declared_capabilities`, `admitted_capabilities`, `instantiated_capabilities`, and `used_capabilities` distinctly in provenance.
4. Preserve blocked-call `denial_class` distinctly in provenance and in the audit artifact instead of collapsing blocked outcomes into one generic failure shape.
5. Add one canonical audit-artifact producer for schema `extension_capability_audit.v1`; it must write one stable output path and use the rerun diff-ledger contract.
6. Require `side_effect_observed=false` on all authorization rejections.

### Exact code surfaces

1. `orket/extensions/artifact_provenance.py`
2. `docs/architecture/event_taxonomy.md`
3. one canonical script under `scripts/extensions/` or `scripts/governance/` for the durable audit artifact
4. the runtime event emission seam chosen in Workstream 1

### Exit criteria

1. Blocked, successful, and exceptional first-slice capability calls emit the required telemetry family.
2. Provenance and audit outputs record declared, admitted, instantiated, and used sets distinctly.
3. Blocked-call provenance and audit rows preserve `denial_class` distinctly.
4. One canonical artifact command and stable path exist for `extension_capability_audit.v1`.
5. Deny and allow cases are represented as separate exercised rows in the audit artifact.

## Workstream 3 - First-slice proof and authority sync

### Goal

Close the first slice without overstating coverage.

### Tasks

1. Add contract and integration proof for parent-to-child identity preservation, invocation denial, admitted read and write separation, and drift failure.
2. Keep requirements, spec, roadmap, and extension-validation wording aligned in the same change.
3. Do not widen the closure claim beyond `model.generate`, `memory.query`, and `memory.write`.

### Required proof commands

1. `python -m pytest -q tests/runtime/test_extension_components.py`
2. `python -m pytest -q tests/runtime/test_extension_manager.py`
3. `python -m pytest -q tests/core/test_runtime_event_logging.py`
4. one canonical audit-artifact command frozen in the implementation change

### Exit criteria

1. The real subprocess path proves admitted read without write and admitted write without read.
2. The real subprocess path proves undeclared use denial, declared-but-not-admitted denial, and child-side drift failure.
3. Telemetry and audit outputs match the frozen contract names and vocabulary.
4. The docs no longer imply that capability preflight alone is authorization.

## Slice binding rule

No implementation slice under this plan is specific enough unless it names:
1. the exact capability families or capability ids it touches
2. the exact parent and child runtime seams it changes
3. the denial truth it introduces or refines
4. the proof commands that must pass
5. the doc and spec updates that land in the same change

## First-slice completion bar

This first slice is complete only when all of the following are true:
1. the parent computes one admitted capability decision and serializes it in a host-issued authorization envelope
2. the child revalidates that envelope before workload code executes
3. `model.generate`, `memory.query`, and `memory.write` enforce declared versus admitted authority at invocation time
4. `memory.query` and `memory.write` can be admitted independently
5. undeclared use, declared-but-not-admitted use, and authorization drift fail closed without side effects
6. runtime emits the required `sdk_capability_call_*` telemetry family
7. provenance and the durable audit artifact record declared, admitted, instantiated, and used capability sets distinctly
8. roadmap, requirements, spec, and event-taxonomy surfaces tell one authority story
9. the lane still makes no claim yet about voice, TTS, audio, or turn-control families

If execution stops short, this plan must stay as the checkpoint authority and record exactly which workstream exit criteria remain open.

## Deferred follow-on after first slice

1. `speech.transcribe`
2. `tts.speak`
3. `audio.play`
4. `speech.play_clip`
5. `voice.turn_control`
6. any broader capability-family policy generalization beyond what the first slice proves
