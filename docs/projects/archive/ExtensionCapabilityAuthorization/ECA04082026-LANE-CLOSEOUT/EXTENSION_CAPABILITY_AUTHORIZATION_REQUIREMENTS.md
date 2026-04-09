# Extension Capability Authorization Requirements

Last updated: 2026-04-08
Status: Active live requirements authority
Owner: Orket Core
Related authority:
1. `docs/ARCHITECTURE.md`
2. `docs/ROADMAP.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/projects/ExtensionCapabilityAuthorization/EXTENSION_CAPABILITY_AUTHORIZATION_IMPLEMENTATION_PLAN.md`
5. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
6. `docs/specs/TOOL_EXECUTION_GATE_V1.md`
7. `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`
8. `orket/extensions/workload_executor.py`
9. `orket/extensions/workload_artifacts.py`
10. `orket/extensions/sdk_workload_subprocess.py`

## Authority posture

This file is the live requirements authority for the open Extension Capability Authorization lane.

It is not implementation authority.
The canonical implementation plan now lives at `docs/projects/ExtensionCapabilityAuthorization/EXTENSION_CAPABILITY_AUTHORIZATION_IMPLEMENTATION_PLAN.md`.
Roadmap execution for this lane now attaches through that implementation plan.

The durable planning contract for this lane now lives in `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`.

The earlier future-lane stub under `docs/projects/future/Next/04_EXTENSION_CAPABILITY_AUTHORIZATION_REQUIREMENTS.md` no longer acts as lane authority.

## Purpose

Define one host-owned authorization contract for SDK capability invocation so extension capability use can become as explicit and fail-closed as the governed turn-tool path without pretending capability preflight alone is equivalent to tool execution gating.

## Problem

SDK capability registry invocations inside extension workloads are not the same authorization model as governed tool dispatch.

Current extension runtime behavior is split:
1. engine-delegated run actions can normalize back into `run_card(...)` and therefore re-enter the canonical governed runtime path
2. SDK workloads build a live `CapabilityRegistry`, preflight declared capabilities, then hand capability providers into workload code while the subprocess rebuilds a capability registry again from request context

Those are different authority stories and must not be closed under one false-hot requirements claim.

## Frozen split

1. Engine-delegated extension actions that normalize into `run_card(...)` stay in the Tool Gate Enforcement lane.
2. SDK capability registry invocations such as `model.generate`, `memory.write`, `memory.query`, `speech.transcribe`, `tts.speak`, `audio.play`, and `voice.turn_control` are tracked in this lane instead.
3. Validation success under `orket ext validate <extension_root> --strict --json` does not grant SDK capability execution authority.

## Frozen authorization decisions

1. Canonical authorization seam: `host_authorized_capability_registry_v1`.
2. Capability preflight is admissibility checking only. It is not runtime authorization.
3. The host computes `admitted_capabilities` before subprocess execution.
4. The subprocess must consume and revalidate a host-issued authorization envelope.
5. Child-side capability expansion beyond the admitted set is forbidden and must fail closed with stable code `E_SDK_CAPABILITY_AUTHORIZATION_DRIFT`.
6. `declared_capabilities`, `admitted_capabilities`, `instantiated_capabilities`, and `used_capabilities` are distinct first-class vocabularies.
7. Capability auto-registration is non-authoritative implementation convenience only.
8. `memory.query` and `memory.write` are separate authorities even when implemented by the same provider.
9. `path_root` identifiers such as `workspace.root` and `artifact.root` are host-issued structural context authority, not ordinary invocation capabilities.
10. Validation success under `orket ext validate <extension_root> --strict --json` remains declaration admissibility evidence only and grants no runtime capability execution authority.

## Authorization envelope

The host-issued authorization envelope for SDK workload execution must include:
1. `extension_id`
2. `workload_id`
3. `run_id`
4. `declared_capabilities`
5. `admitted_capabilities`
6. `authorization_basis`
7. `policy_version`
8. `authorization_digest`

The child process must revalidate that envelope against the child-instantiated capability registry before workload code executes.
The child may validate envelope identity against the child-instantiated capability registry, but it must not mint, recompute, or widen `admitted_capabilities` on its own.

If the child-instantiated registry would expand executable authority beyond `admitted_capabilities`, execution must fail closed with `E_SDK_CAPABILITY_AUTHORIZATION_DRIFT`.
That failure must not collapse into generic missing-capability behavior.

## Authorization vocabulary

1. `declared_capabilities`: capability identifiers declared by the extension manifest.
2. `admitted_capabilities`: capability identifiers authorized by the host for the selected run.
3. `instantiated_capabilities`: capability identifiers actually present in the child capability registry.
4. `used_capabilities`: capability identifiers actually invoked during workload execution.

These vocabularies are not interchangeable and must be recorded distinctly in telemetry and proof artifacts.

## Capability families

Invocation families:
1. `model_io`
   1. `model.generate`
2. `memory_read`
   1. `memory.query`
3. `memory_write`
   1. `memory.write`
4. `voice_input`
   1. `speech.transcribe`
5. `voice_output`
   1. `tts.speak`
   2. `audio.play`
   3. `speech.play_clip`
6. `turn_control`
   1. `voice.turn_control`

Structural context authority:
1. `workspace.root`
2. `artifact.root`

Structural context authority is host-issued execution context, not ordinary invocation authority, and must not be treated as proof that an executable capability was authorized.

## Deny truth classes

The authorization contract must preserve distinct denial and failure classes:
1. `declared_invalid`
   - manifest declares an unknown or forbidden capability identifier
2. `undeclared_use`
   - workload attempts to use a capability not present in `declared_capabilities`
3. `denied`
   - capability was declared but not admitted by host policy for the run
4. `admitted_unavailable`
   - capability was admitted but no usable provider was available at runtime
5. `authorization_drift`
   - child-instantiated capability surface diverges from the host-issued admitted set

These classes must not collapse into generic missing-capability behavior.

## Telemetry requirements

The runtime must emit capability-authorization telemetry for SDK workload execution.

Required event names:
1. `sdk_capability_call_start`
2. `sdk_capability_call_blocked`
3. `sdk_capability_call_result`
4. `sdk_capability_call_exception`

Required fields:
1. `extension_id`
2. `workload_id`
3. `run_id`
4. `capability_id`
5. `capability_family`
6. `authorization_basis`
7. `declared`
8. `admitted`
9. `side_effect_observed`

For `sdk_capability_call_blocked`, `side_effect_observed` must be `false`.

## Audit artifact

The lane must publish a durable JSON audit artifact with schema `extension_capability_audit.v1`.

Each row must include at least:
1. `test_case`
2. `extension_id`
3. `workload_id`
4. `authorization_surface`
5. `declared_capabilities`
6. `admitted_capabilities`
7. `instantiated_capabilities`
8. `used_capabilities`
9. `authorization_basis`
10. `policy_version`
11. `authorization_digest`
12. `expected_result`
13. `observed_result`
14. `denial_class`
15. `proof_ref`

`expected_result` and `observed_result` must describe the same exercised case.
Deny and allow cases must not be mixed in one row.
`denial_class` must preserve the observed deny truth when a case blocks for authorization reasons and must not collapse multiple deny classes into one generic blocked outcome.

Blocked-call provenance must preserve the observed `denial_class`.

## First implementation slice

The first implementation slice is limited to:
1. `model.generate`
2. `memory.query`
3. `memory.write`

This slice must prove:
1. admitted read without write
2. admitted write without read
3. deny of undeclared use
4. deny of declared-but-not-admitted use
5. child-side authorization drift failure

## Cross-authority sync

In the same document pass that activates this lane authority:
1. `docs/specs/TOOL_EXECUTION_GATE_V1.md` must reference `docs/projects/ExtensionCapabilityAuthorization/EXTENSION_CAPABILITY_AUTHORIZATION_REQUIREMENTS.md` as the active requirements source for SDK capability authorization.
2. No authority file may continue pointing SDK capability authorization at the retired future-lane stub.

## Current lane objective

This lane exists to answer:
1. what the canonical SDK capability authorization surface should be
2. how the host-issued admitted capability decision survives subprocess execution without drift
3. which capability families need one shared admission contract versus capability-specific rules
4. what proof is required before SDK capability invocation can make a truthful fail-closed runtime claim
5. how this authorization story stays subordinate to host-owned runtime authority and extension validation authority
