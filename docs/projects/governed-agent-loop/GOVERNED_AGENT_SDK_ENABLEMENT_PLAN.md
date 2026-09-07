# Governed Agent SDK Enablement Plan

Last updated: 2026-09-07
Date: 2026-09-06
Status: Active implementation workstream
Owner: Orket Core
Coordinating authority: `docs/projects/governed-agent-loop/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`
Durable contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`

## Objective

Extend `orket_extension_sdk` so an external extension can implement a bounded,
multi-model agent strategy without importing host-private `orket.*` modules,
owning loop authority, executing effects directly, or receiving provider
credentials.

The SDK is the public contract bridge. It is not the scheduler, control plane,
provider supervisor, or source of execution truth.

## Product outcome

An external SDK workload can:

1. receive one host-issued agent iteration request;
2. invoke one or more admitted host model profiles;
3. query or propose writes to explicitly scoped memory;
4. return structured observations, advisory proposals, effect requests,
   progress claims, handoffs, and a completion recommendation;
5. observe cancellation and bounded runtime inputs;
6. do all of the above through a versioned public API that the host can validate
   and govern.

## Authority boundary

The SDK may expose:

1. immutable input and result models;
2. provider-neutral capability protocols;
3. cancellation and progress-reporting contracts;
4. canonical serialization and validation helpers;
5. extension-focused fixtures and conformance helpers.

The SDK must not expose authority to:

1. continue or resume the loop;
2. approve, execute, or reconcile an effect;
3. expand budgets or capability grants;
4. select raw provider endpoints or access credentials;
5. declare objective completion authoritative;
6. mutate control-plane records directly.

## Activation-time constraints and current disposition

The numbered constraints below record the starting state. Slices 0-1 have now
closed items 1-9 with immutable public bindings, async workload and cancellation
contracts, framed IPC, live child proxies, the complete packaged schema and
semantic validator, strict feature negotiation, clean built-package proof, and
standalone SDK namespace ownership. The built external-package and live-provider
proof is now recorded for Slices 3-5; final release proof remains Slice 7 work.

1. `WorkloadContext` exposes only run identity, directories, seed, config, and
   capabilities; it has no attempt, iteration, checkpoint, budget, lease,
   cancellation, or parent-lineage context.
2. The public `Workload` protocol is synchronous, while the host subprocess
   path only tolerates awaitables as an implementation detail.
3. `model.generate` exposes one provider and a single system-prompt/user-message
   request. It cannot request multiple admitted model profiles, structured
   output, message history, tool schemas, streaming, or per-call budgets.
4. `WorkloadResult` cannot distinguish observations, proposals, requested
   effects, progress claims, completion recommendations, and handoffs.
5. Controller workload v1 is intentionally sequential, depth-one, bounded
   fan-out and fail-fast. It is not an agent-loop contract.
6. The current `v0` workload model has typed agent declarations, but generic
   entries still discard unknown metadata and accept an agent capability marker
   without an agent kind. Required-feature presence is checked; actual host
   feature support and the live handshake are not yet negotiated.
7. The current child constructs providers and returns a capability report after
   execution. It has no live parent broker for per-call budget admission,
   cancellation, or host-owned provider receipts.
8. The packaged schema is an initial Slice 0 binding, not complete contract
   coverage. The S0-B gap list in the coordinating plan gates public SDK types.
9. Core package discovery includes `orket_extension_sdk`, while the standalone
   SDK distribution owns the same namespace. A mixed installed environment and
   the SDK/core compatibility window are not yet proven.

## Design locks

1. Add a separate agent-workload contract; do not widen
   `controller.workload.v1` into a loop runtime.
2. An extension requests a model profile or capability class. The host resolves
   the actual provider, endpoint, model, credentials, and capacity admission.
3. Extension-returned effects are proposals only and must enter an existing
   host-governed effect path.
4. Extension-returned `continue`, `pause`, `stop`, or `complete` values are
   recommendations only.
5. Durable semantic contracts live in accepted specs and schemas; SDK models
   are public bindings verified against that authority, not a parallel schema.
6. Existing SDK compatibility rules in `docs/requirements/sdk/VERSIONING.md`
   remain active. Any necessary break requires an explicit compatibility delta
   and migration path.
7. Agent extensions must use only public SDK imports. Import scans and Python
   import guards enforce authoring rules; they are not an OS security boundary.

`agent.iteration.v1` is the required broker-backed protocol capability for an
agent workload. The host materializes its public SDK proxy only after binding
the invocation, budgets, fencing generation, and cancellation state. It is not
an effect permission and may not be self-admitted by child configuration.

The selected child transport is `agent_stdio_ipc.v1`: four-byte big-endian
length-prefixed UTF-8 JSON over subprocess stdin/stdout, with stdout reserved
for protocol frames and bounded diagnostics drained separately from stderr.
The canonical framing, identity, cancellation, and teardown rules live in
`docs/specs/GOVERNED_AGENT_LOOP_V1.md`.

## Workstream 0 - Contract and compatibility decisions

1. Requirements acceptance completed on 2026-09-06.
2. Durable contract extracted to `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.
3. Define one canonical JSON representation for:
   - agent iteration request;
   - agent iteration result;
   - model-profile request and resolved-use receipt;
   - effect proposal;
   - agent handoff;
   - budget and usage snapshot;
   - cancellation and progress event.
4. Implement additive agent declarations within `manifest_version: v0`, require
   the new `agent.iteration.v1` capability in the existing required-capabilities
   field, and require a live host-issued iteration handshake. An older strict
   validator must refuse the unknown capability before invocation; a permissive
   host must fail at the agent entrypoint before model or effect work.
   The new SDK validator must also reject unknown fields inside the typed agent
   declaration so misspelled policy, budget, or recovery fields are not discarded.
5. Define SDK/core compatibility and feature negotiation so an extension fails
   closed against a host that does not support its agent contracts.
6. Close the coordinating plan's S0-A/S0-B gates before promoting this workstream:
   validate agent kind, capability marker, input/output versions, and declaration
   consistently; distinguish required-feature syntax from host support. Do not
   admit an unknown required feature just because the two V1 markers are present.
7. Treat serialized manifests and reloaded catalog entries as validation inputs,
   not already-trusted model instances. Bound and validate role/profile mappings,
   reject ambiguous duplicate roles, and preserve generic v0 compatibility only
   for entries that do not claim the agent protocol.

Acceptance gates:

1. Each object has one schema authority and stable version identifier.
2. Unknown versions and unknown enum values fail closed.
3. No public SDK model imports control-plane implementation types.
4. Existing supported SDK extensions retain the documented compatibility SLA or
   receive an explicitly approved migration.
5. Test old host/old SDK, old host/new SDK, new host/old extension, and matching
   agent versions from built distributions. Record actual compatible versions;
   a minor SDK bump alone does not prove the published core compatibility SLA.
6. Negative admission fixtures include marker-only generic entries, agent
   input/output versions without the kind, missing or misspelled declarations,
   unsupported features, stripped legacy metadata, and malformed catalog reloads.
   Author-validator acceptance is never evidence that a host supports execution.

## Workstream 1 - Agent iteration models

Add typed public models equivalent to the following semantic split:

1. `AgentIterationRequest`
   - objective and acceptance references;
   - stable run, attempt, and iteration identity;
   - authoritative context and prior verified-output references;
   - bounded materialized contents or a specified read-only broker resolver for
     those references, including the objective and acceptance basis;
   - admitted capability and model-profile requests;
   - remaining budget and deadline snapshot;
   - accepted checkpoint and recovery posture;
   - agent/team configuration supplied by the extension manifest.
2. `AgentIterationResult`
   - observations;
   - advisory proposal;
   - effect proposals;
   - claimed progress and supporting references;
   - completion recommendation and evidence references;
   - handoff proposals;
   - scoped memory-write proposals and provenance;
   - model and output usage;
   - normalized failure or blocked reason.

The result contract must prevent a generic `ok=true` from being confused with
verified objective success.

Acceptance gates:

1. Round-trip canonical serialization is deterministic.
2. SDK validation rejects malformed identity and oversized content; only the
   host resolves reference ownership, existence, and evidence trust.
3. Tests prove that advisory completion cannot deserialize as authoritative
   final truth.
4. Every required semantic field maps to the packaged schema or an explicitly
   referenced canonical contract. Shared fixtures exercise null/unknown usage,
   boundary sizes, duplicate roles, nested identity mismatch, invalid deadlines,
   and impossible status/usage combinations in both SDK and host validation.
5. Canonical schema loading/validation is async-safe at runtime: load outside
   the event loop or offload resource I/O and bounded validation explicitly.
   A frozen model containing mutable lists/dicts is not deep immutability proof.

## Workstream 2 - Async lifecycle, cancellation, and progress

1. Add an explicitly asynchronous workload protocol rather than relying on
   runtime inspection of a synchronous protocol result.
2. Preserve the current synchronous protocol only within the published SDK
   compatibility contract; do not add an untracked compatibility shim.
3. Add a host-issued cancellation view that extension code may observe but not
   clear or replace.
4. Add bounded progress events with sequence, run, iteration, and trace identity.
5. Define subprocess termination behavior for cooperative cancellation,
   cancellation timeout, forced termination, and missing final result.
6. Ensure partial progress never becomes terminal workload success.
7. Put capability calls and cancellation on a bounded host/child IPC channel;
   carry invocation id, call id, contract version, and framing length. Parent
   authorization comes from its retained invocation binding, not child fields.
8. Keep raw providers, credentials, memory stores, and budget counters in the
   host. Child SDK proxies carry requests and host receipts only. Use a
   sanitized environment and separate bounded diagnostic output from protocol
   frames; reject late, malformed, duplicate-conflicting, and oversized frames.
9. Specify the complete frame/operation schemas and handshake state machine in
   Slice 0; build the shared codec and child proxies in Slice 1. Exercise them
   against the minimum real host broker in Slice 2 before live model integration.
   Define partial-frame/deadline handling, strict JSON decoding, aggregate output
   bounds, and platform-specific process-tree teardown, not only a per-frame cap.

Acceptance gates:

1. Cancellation interrupts a blocked async workload and reaps the extension
   subprocess tree; provider work that cannot be confirmed stopped retains
   explicit uncertain capacity state in the host.
2. Progress emission is bounded and cannot mutate execution authority.
3. Timeout and cancellation remain distinct stable outcomes.
4. Broker disconnect denies new calls. Cooperative cancellation has a bounded
   grace period, then the host terminates and awaits the child/process tree.
   Provider work that cannot be confirmed stopped retains an uncertain capacity
   reservation instead of falsely reporting that inference ceased.

## Workstream 3 - Multi-profile model capability

Add a versioned agent model protocol beside the existing `model.generate`
contract, with a provider-neutral request model that can express:

1. host-defined model profile reference or required model capability class;
2. structured messages with bounded roles and content;
3. response schema or response mode;
4. maximum input/output budget and timeout;
5. temperature, seed request, and stop conditions when host policy admits them;
6. tool-description input for proposal generation without tool execution;
7. trace, iteration, and role identity;
8. streaming preference with a bounded non-streaming fallback contract.

The response must record actual host-resolved model/profile identity, usage,
latency, truncation, finish reason, and capability posture without exposing
credentials.

The current `agent_model_profile_request` selects a profile; it does not carry
model messages or generated content. Bind actual call request/result shapes and
their broker operation explicitly before adding proxies. Do not overload profile
selection or use unvalidated arbitrary configuration as the model-call protocol.

Acceptance gates:

1. One workload can request distinct planner, actor, and critic profiles.
2. The host can deny or substitute a profile without the extension bypassing the
   decision.
3. Usage totals reconcile with the enclosing iteration budget.
4. Unsupported tool/JSON/streaming behavior is explicit rather than silently
   downgraded.
5. Host admission reserves input plus bounded output usage before a call. Every
   retry, repair, and timed-out request consumes a call allocation; missing
   provider usage is explicitly unknown and conservatively charged, never zero.
6. Extension usage is advisory telemetry. Budget truth comes from host broker
   records and provider observations even if the child dies before returning.
7. Represent measured counts, named estimates, unknown counts, and conservative
   host charges distinctly. Test missing/partial provider usage and child death;
   neither zero-filled counts nor a child-returned receipt may release reserved
   capacity or overwrite durable host call records.

## Workstream 4 - Effect, handoff, memory, and continuation proposals

1. Define an effect-proposal model carrying capability, intended target,
   complete bounded arguments or their immutable artifact ref, arguments digest,
   idempotency input, and evidence refs. A digest alone is not executable input.
2. Deliver host effect receipts in the following iteration request after result
   validation and effect governance; receipts do not synchronously execute an
   extension's proposal while it is still constructing its result.
3. Define handoff proposals with source role, target role/profile, scope,
   artifact refs, provenance, and narrowed capability/budget request.
4. Extend memory requests with objective, agent-private, and explicitly shared
   team scopes while retaining host-owned write policy.
   Within one extension process, role labels filter context but do not isolate
   secrets. Memory writes are proposals committed by the host after validation.
5. Define continuation recommendations and normalized reasons without granting
   continuation authority.

Acceptance gates:

1. Undeclared effect, memory, or handoff use fails with a distinct authorization
   class.
2. Raw conversation history is not accepted as a trusted handoff substitute.
3. Effect receipts link to host authority without embedding host-private record
   implementations in the SDK.

## Workstream 5 - Manifest, validation, templates, and documentation

1. Add the minimum manifest declarations needed for agent workloads:
   - workload kind and input/output contract versions;
   - requested model profiles/capability classes;
   - required capabilities;
   - recovery posture;
   - bounded resource requirements.
2. Update SDK validation, import scanning, host validation, author guide, and the
   external extension template in the same contract change.
3. Add test helpers for iteration fixtures, fake host capabilities, cancellation,
   budget exhaustion, denied effects, and canonical-result comparison.
4. Document a minimal external agent workload without internal imports.
5. Use the two-batch JSON ticket-report fixture from the coordinating plan in
   shared SDK/host helpers and the template. No private test-helper imports from
   Orket are permitted in the external extension.

Acceptance gates:

1. Clean-environment author validation and host validation pass from the built
   SDK wheel.
2. Unsupported hosts reject the new workload contract with a stable diagnostic.
3. The reference extension can be developed entirely from published SDK docs
   and types.

## Workstream 6 - Proof and release

Build development wheels during Slice 1 and install them into the host and
external fixture environments by exact artifact path/digest. Complete the
release gates below after joint host/extension proof; they are not prerequisites
for starting that proof. Package the canonical wire schemas with the SDK so a
clean installation never needs a repository-relative `docs/` path. Verify host
and SDK bindings against those same schema bytes rather than copying schemas.

Before distributing the first development wheel:

1. assign a prerelease SDK version and record exact supported core artifacts.
   At this checkpoint SDK `0.1.0` and core `0.5.9` are outside the formula in
   `docs/requirements/sdk/VERSIONING.md`; do not claim compatibility from source
   tests or pick a minor bump without checking the resulting window;
2. decide and document one installed owner for the `orket_extension_sdk`
   namespace. Resolve the core/standalone packaging overlap before mixed pinned
   installs; install order must not choose contract or schema authority;
3. build wheel and sdist in isolated build directories, install without editable
   paths into clean environments outside the checkout, and record imported
   module paths, versions, artifact digests, and canonical schema digests;
4. prove the supported install/upgrade flow and strict external validation.
   Do not count source-tree imports or merely listing wheel contents as clean
   installation proof. Update packaging/versioning authorities in the same
   implementation change if their behavior or compatibility window changes.

Required test classification:

1. `unit`: normalization, canonical serialization, budget math, and helpers.
2. `contract`: schemas, version negotiation, capability declarations, and
   fail-closed validation.
3. `integration`: host capability registry, subprocess execution, cancellation,
   and effect-proposal routing.
4. `end-to-end`: built SDK wheel installed into a clean external-extension
   environment and exercised through `orket ext validate` plus one governed
   iteration.

Required release proof:

1. SDK tests and lint pass.
2. Wheel and source distribution build successfully.
3. Clean-environment install and public-import smoke pass.
4. SDK tag/version guard passes.
5. Changelog names new contracts, compatibility window, and migration behavior.

## Completion criteria

This plan is complete only when:

1. the public SDK can represent every input and output needed by the accepted
   single-agent loop contract;
2. the reference extension uses no private host imports;
3. multiple admitted local-model profiles can be requested in one iteration;
4. effects and continuation remain host-owned;
5. cancellation, budgets, and malformed payloads fail closed;
6. the clean-environment end-to-end proof passes;
7. the user accepts the SDK proof and author experience.

## Non-goals

1. A general distributed-agent protocol.
2. Provider process or GPU lifecycle management in the SDK.
3. Credentials, raw provider endpoints, or control-plane repositories exposed to
   extensions.
4. Dynamic unrestricted capability or budget expansion.
5. Replacing controller workload v1.
