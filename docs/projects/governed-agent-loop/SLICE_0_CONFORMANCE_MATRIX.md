# Governed Agent Loop Slice 0 Conformance Matrix

Last updated: 2026-09-07
Status: Slice 0 closed; updated after deterministic Slice 2 admission
Owner: Orket Core

## Decisions resolved

1. Context delivery: host-materialized bounded values accompany every objective,
   acceptance, authoritative-context, and prior-output reference. No read-only
   resolver is admitted in V1.
2. Usage: measured, estimated, and unknown observations are distinct from host
   charges. Unknown observations use null counts and conservative charges.
3. Policy and budgets: immutable referenced/digested snapshots carry every
   minimum limit family; zero remains a valid exhausted or unused allocation.
4. Models: profile selection and an actual message-bearing model call are
   separate request/result contracts. Receipts contain actual resolution and
   host-owned usage truth without provider credentials or raw endpoints.
5. Memory, handoff, and effects: memory queries are bounded broker calls;
   memory writes, handoffs, and effects are typed proposals. Effect receipts
   arrive on a later iteration after host governance.
6. Packaging: Slice 1 uses SDK `0.5.0a1`; clean built-artifact inspection proves
   the standalone SDK is the sole installed owner of `orket_extension_sdk`.

## S0-A: fail-closed admission

| Boundary | Implementation | Evidence |
| --- | --- | --- |
| Author validation | `agent_discriminator_reasons()` examines raw rows before permissive v0 parsing can erase markers; all agent-like rows require the complete typed declaration. | Contract cases cover reserved id, capability-only, input-only, output-only, and alternate-version markers. |
| Host validation | `orket ext validate` supplies the two implemented governed-agent host features. | Complete V1 declarations pass; unknown or missing features and inconsistent agent markers fail closed. |
| Install | Installation revalidates the parsed SDK manifest against the implemented host features before catalog publication. | Admission tests prove valid publication and malformed/unsupported refusal. |
| Catalog reload | Raw persisted rows are classified and strictly revalidated before conversion into host entries. | Marker-only persisted catalog fixture fails closed. |
| Invocation | The generic executor applies the same raw discriminator set before artifact allocation. | Existing direct executor test plus marker-only coverage. |
| Child capability config | `agent.iteration.v1` is host-bound and rejected in child capability configuration. | Direct capability-registry test observes the stable refusal. |

## S0-B: requirement-to-binding map

| Durable requirement | Canonical representation | Semantic owner / negative fixture |
| --- | --- | --- |
| Every limit family | `agent_budget_snapshot.v1` includes iteration, time, model/token, role, effect/capability, output/artifact byte, repair/failure, repeated/no-progress, and concurrency counters. | SDK checks snapshot digest, scope, duplicates, allocations, and iteration-vs-run limits; fixtures cover duplicates and boundaries. |
| Usage truth | `usage_posture`, nullable observations, named estimate source, and separate charged counters on usage and receipts. | JSON Schema rejects missing known counts and invented unknown counts; positive fixtures cover measured zero and unknown conservative charges. |
| Actual model calls | `agent_model_call_request.v1` carries messages, response mode/schema, call/role identity, tools, stop conditions, and call budgets; result and receipt carry content plus actual resolution. | Schema and semantic validators reject identity/call/digest mismatch. |
| Context usability | `materialized_inputs` exactly covers objective, acceptance, context, and prior-output refs with kind, encoding, byte count, digest, and provenance. | Semantic validator rejects missing/extra refs, kind mismatch, invalid base64, byte mismatch, and digest mismatch. Host remains owner of existence/trust. |
| Effects | Proposal includes lineage identity, namespace, complete args or immutable ref, digest, idempotency, target, and evidence. Later request carries typed host effect receipts. | SDK validates inline argument digest; host request/result validator checks capability, namespace, and budgets. |
| Memory/handoff | Bounded query request/result, scoped write proposal with provenance, and handoff proposal with profile/capability/budget narrowing. | Shared schema; runtime authorization remains Slice 2/4 work. |
| General wire bounds | One-MiB payload, depth 32, strict object fields, stable versions/enums, unique ids/roles/refs, format-checked deadlines, and nested identity equality. | Shared invalid fixture corpus runs through SDK and host-facing tests. |

## S0-C: governed invocation definition

The durable contract now fixes the seven frame messages, direction, handshake,
sequence/call rules, partial-frame behavior, `model.call.v1` and
`memory.query.v1` operations, cancellation, and bounded teardown.

`orket/application/services/governed_agent_ports.py` defines:

1. the retained parent run/attempt/step/fence/cancellation/deadline binding;
2. idempotent dispatch preparation;
3. one-shot lower-level child invocation without independent-run publication;
4. atomic result acceptance against the retained binding;
5. interrupted-publication and uncertainty recording;
6. host-owned broker dispatch and cancel/reap behavior.

Slices 1-2 implement these ports in the application-owned governor and durable
repository, advertise `governed_agent_loop.v1` and `agent_stdio_ipc.v1`, and
admit them only through the dedicated governed-agent catalog path. The generic
extension executor continues to fail closed before run-artifact allocation.

## S0-D: reproducible contract proof

Positive and negative fixtures live in
`orket_extension_sdk/agent_fixtures.py`. Both SDK contract tests and host-facing
admission/semantic tests import those builders. Slice 1 executed the applicable
built-package checks in clean environments outside the checkout:

| Core host | SDK/extension | Expected result |
| --- | --- | --- |
| Last pre-agent strict host artifact | Agent extension built with `0.5.0a1` | Refuse unknown `agent.iteration.v1` before invocation. |
| Current core artifact | Existing non-agent SDK artifact | Existing supported validation and generic invocation posture remains green. |
| Pre-broker Slice 0 host artifact | Agent extension built with `0.5.0a1` | Historical expected refusal: author validation passes; host validation/install refuses unavailable features. |
| Current Slice 2 broker host artifact | Agent extension built with the pinned `0.5.0a1` development wheel | Matching handshake and deterministic two-iteration proof passed. |

Every row records wheel/sdist digest, imported module path, SDK/core version and
commit, schema digest, validation command, and observed refusal/success. Source
imports and wheel-content listings are not clean-install proof.

## Architecture checklist

| Check | Result | Evidence / remediation |
| --- | --- | --- |
| AC-01 Dependency Direction | pass | New SDK contract modules import no private `orket.*`; application ports depend only on standard/public contract types. |
| AC-02 Decision Node Purity | pass | No decision node changed. |
| AC-03 Explicit Input Contracts | pass | Invocation binding, request payload, result, cancellation, budgets, and calls are explicit. |
| AC-04 Deterministic Runtime Inputs | pass | No runtime clock/random source added; deadline, lease, sequence, and identity are supplied values. |
| AC-05 Side-Effect Ownership | pass | SDK exposes only queries and proposals; application ports retain publication and broker authority. |
| AC-06 Adapter Side-Effect Classification | pass | The child adapter performs broker queries only; extension effects remain proposals. |
| AC-07 Runtime Truth Claims | pass | Host features are advertised only for the dedicated proven path; proof output says `deterministic_fixture_not_live_model`. |
| AC-08 Observability Schema Authority | pass | No runtime event field changed. |
| AC-09 Replayability Evidence | pass for Slice 2 | Durable decisions, digests, accepted results, final truth, and non-mutating replay are proven for the deterministic two-iteration path. |
| AC-10 Authority Drift Control | pass | Durable spec, delta, current authority, plan state, schema, validators, and tests are updated together. |
