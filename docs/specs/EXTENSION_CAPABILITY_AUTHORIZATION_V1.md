# Extension Capability Authorization V1

Last updated: 2026-04-23
Status: Active (implemented shipped-slice authority)
Owner: Orket Core
Archived lane requirements: `docs/projects/archive/ExtensionCapabilityAuthorization/ECA04082026-LANE-CLOSEOUT/EXTENSION_CAPABILITY_AUTHORIZATION_REQUIREMENTS.md`
Implementation closeout authority: `docs/projects/archive/ExtensionCapabilityAuthorization/ECA04082026-LANE-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/ARCHITECTURE.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/TOOL_EXECUTION_GATE_V1.md`
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`

## Authority posture

This document is the durable contract authority for the shipped Extension Capability Authorization slice.

It freezes:
1. the canonical SDK capability authorization seam
2. the host-to-child authorization envelope contract
3. the capability authorization vocabulary and family matrix
4. the deny-truth, telemetry, and audit-artifact contract for the shipped slice
5. the shipped-slice control-plane execution publication boundary inside extension workload runs

The implemented scope is limited to the shipped slice:
1. host-issued authorization envelopes
2. child-side revalidation across the subprocess boundary
3. governed runtime enforcement for `model.generate`, `memory.query`, `memory.write`, `speech.transcribe`, `tts.speak`, `audio.play`, `speech.play_clip`, and `voice.turn_control`
4. emitted `sdk_capability_call_*` telemetry plus provenance and the canonical audit artifact
5. first-class control-plane publication of extension workload start, shipped-slice capability-call steps/effects, pre-effect checkpoint, closeout, and terminal final truth

This document does not claim that SDK capability registry invocation is part of the governed tool-dispatch lane.

## Purpose and scope

Define one host-owned authorization surface for SDK workload capability invocation.

This contract applies to SDK capability registry invocations inside extension workloads.
It does not replace the canonical governed turn-tool gate described by `docs/specs/TOOL_EXECUTION_GATE_V1.md`.

## Canonical seam

The canonical SDK capability authorization seam is:
1. `host_authorized_capability_registry_v1`

That seam is the host-owned composition of:
1. manifest-declared `required_capabilities`
2. host capability-family policy
3. host runtime context policy
4. host-built provider registry
5. host-issued authorization envelope consumed by the subprocess

Capability preflight is admissibility checking only.
It is not runtime authorization.

## Authority split with Tool Gate Enforcement

1. Engine-delegated extension actions that normalize into `run_card(...)` remain governed by `docs/specs/TOOL_EXECUTION_GATE_V1.md`.
2. SDK capability authorization is a separate lane because capability registry invocation is not the same authority model as governed tool dispatch.
3. The shipped slice now publishes its runtime execution into the enclosing extension workload control-plane run/effect boundary, but that does not make capability registry invocation part of the governed tool-dispatch lane.
4. Validation success under `orket ext validate <extension_root> --strict --json` remains declaration admissibility evidence only and does not grant runtime capability execution authority.

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

The parent computes `admitted_capabilities` before subprocess execution.

The child process must consume and revalidate the host-issued authorization envelope against the child-instantiated capability registry before workload code executes.
The child may validate envelope identity against the child-instantiated capability registry, but it must not mint, recompute, or widen `admitted_capabilities` on its own.

If the child-instantiated registry would expand executable authority beyond `admitted_capabilities`, execution must fail closed with stable code `E_SDK_CAPABILITY_AUTHORIZATION_DRIFT`.
That failure must not collapse into generic missing-capability behavior.

## Authorization vocabulary

1. `declared_capabilities`: capability identifiers declared by the extension manifest
2. `admitted_capabilities`: capability identifiers authorized by the host for the selected run
3. `instantiated_capabilities`: capability identifiers actually present in the child capability registry
4. `used_capabilities`: capability identifiers actually invoked during workload execution

These vocabularies are not interchangeable.
They must be recorded distinctly in telemetry, provenance, and proof artifacts.

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

`memory.query` and `memory.write` are separate authorities even when implemented by the same provider.

Capability auto-registration may remain an implementation convenience, but it is non-authoritative.
A capability that is not admitted must be unusable at runtime even if a provider object exists.

## Deny truth classes

The authorization contract must preserve distinct denial and failure classes:
1. `declared_invalid`
2. `undeclared_use`
3. `denied`
4. `admitted_unavailable`
5. `authorization_drift`

Definitions:
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

## Telemetry contract

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

## Blocked-call provenance

When a capability call is blocked for authorization reasons, provenance must preserve the observed `denial_class`.

`denial_class` must distinguish among `declared_invalid`, `undeclared_use`, `denied`, `admitted_unavailable`, and `authorization_drift`.
Blocked-call provenance must not collapse those truths into a generic missing-capability shape.

## Control-plane execution publication

The shipped slice must publish capability execution into the enclosing extension workload control-plane run.

Required publication on the shipped-slice runtime path:
1. one extension workload `RunRecord`, initial `AttemptRecord`, and start `StepRecord`
2. one supervisor-owned pre-effect `resume_forbidden` checkpoint plus acceptance
3. one first-class `StepRecord` plus `EffectJournalEntryRecord` for each shipped-slice capability call in `call_records`
4. one terminal closeout `StepRecord` plus `EffectJournalEntryRecord`
5. one terminal `FinalTruthRecord`

The operator-facing extension workload provenance/result surfaces may summarize that execution state, but they must self-identify as `projection_only` with source `control_plane_records`.

For the shipped first slice, host-owned namespace enforcement must also scope stored SDK profile/session memory rows by extension id on the `memory.query` / `memory.write` path.

## Audit artifact schema

The lane must publish a durable JSON audit artifact with schema `extension_capability_audit.v1`.

Current canonical artifact path and command:
1. `benchmarks/results/extensions/extension_capability_audit.json`
2. `python scripts/extensions/build_extension_capability_audit.py --strict`

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

## Shipped-slice proof requirements

The current shipped slice covers:
1. `model.generate`
2. `memory.query`
3. `memory.write`
4. `speech.transcribe`
5. `tts.speak`
6. `audio.play`
7. `speech.play_clip`
8. `voice.turn_control`

This slice must prove:
1. admitted read without write
2. admitted write without read
3. admitted model generation on a deterministic provider seam
4. admitted voice/audio/turn-control execution across the shipped non-memory families
5. deny of undeclared use
6. deny of declared-but-not-admitted use, including a non-memory capability family
7. child-side authorization drift failure
8. shipped-slice capability calls publish into extension workload control-plane execution/effect truth
9. shipped-slice SDK memory storage stays extension-scoped

Current canonical proof entrypoints:
1. `python -m pytest -q tests/runtime/test_extension_components.py`
2. `python -m pytest -q tests/runtime/test_extension_manager.py`
3. `python -m pytest -q tests/core/test_runtime_event_logging.py`
4. `python -m pytest -q tests/runtime/test_extension_capability_authorization.py`
5. `python -m pytest -q tests/scripts/test_build_extension_capability_audit.py`
6. `python scripts/extensions/build_extension_capability_audit.py --strict`
