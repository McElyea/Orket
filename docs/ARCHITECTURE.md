# Orket Architecture (Target State)

Last updated: 2026-04-08
Status: Active target architecture (transitioning)

Canonical architecture specification for the Orket runtime.

This document defines architectural constraints governing runtime behavior and component responsibilities.
Rules in this document are normative for target-state architecture and for new/modified paths unless a listed transition exception applies.

The architecture is intentionally minimal. Each rule exists to prevent a real systemic failure mode.

## Implementation Status

This document describes the target architecture of the Orket runtime.

The current codebase partially implements these rules and still contains transitional structures that are not yet fully conformant.
Known deviations are documented in `Known Current Exceptions`.

When touching an exception area:
1. Do not widen the exception.
2. Make the smallest reasonable move toward compliance.
3. Keep runtime truth explicit (do not claim compliance where proof is missing).

Current-state operational authority that remains active during migration:
1. `CURRENT_AUTHORITY.md`
2. `docs/architecture/event_taxonomy.md`
3. `docs/specs/REVIEW_RUN_V0.md`

## Known Current Exceptions

As of 2026-04-08, these divergences are known and accepted as transition debt:

1. Dependency layering exceptions:
   1. `orket/interfaces/api.py` imports decision-node registry directly.
   2. `orket/interfaces/coordinator_api.py` and `orket/interfaces/orket_bundle_cli.py` import core/domain types directly.
2. Decision-node purity exceptions:
   1. `orket/decision_nodes/api_runtime_strategy_node.py` and `orket/decision_nodes/builtins.py` still include environment/path/provider policy logic, but API/engine/pipeline construction, env bootstrap, and session-id minting on the touched runtime paths now live in explicit services.
3. API transport compatibility exception:
   1. `orket/interfaces/api.py` still exports minimal module-level compatibility aliases for `engine`, `api_runtime_host`, `stream_bus`, `interaction_manager`, `extension_manager`, and `extension_runtime_service`, but authoritative live ownership now lives on `app.state.api_runtime_context`.
4. Deterministic runtime clock/input exceptions:
   1. Some application paths still use wall-clock helpers directly (for example `time.time()` / `datetime.now(...)`) instead of injected runtime inputs.
5. Replay diagnostics compatibility exception:
   1. `orket/orchestration/engine.py` still exposes `replay_turn()` as a compatibility wrapper, but the canonical engine replay surface is `replay_turn_diagnostics()` and both surfaces are explicitly artifact-backed diagnostics rather than replay-verdict authority.
6. Runtime verification support-artifact compatibility exception:
   1. `runtime_verification.json` remains the latest-path name for verifier support artifacts, but it is not authored-output authority; canonical verifier history now lives through `runtime_verification_index.json` plus per-record artifacts under `runtime_verifier_records/`.
7. Observability schema transition:
   1. `docs/architecture/event_taxonomy.md` remains the canonical event-field authority for current runtime events.
   2. The observability identity model below is target-state and must be versioned during migration.
8. Transitional runtime specifics:
   1. Durable-path defaults and `ReviewRun` v0 notes remain active current-state authority (documented in this file under sections 20 and 24).

## 1. Purpose

Orket is a deterministic runtime designed to integrate volatile model-assisted behavior without allowing that volatility to corrupt authoritative system state.

The architecture enforces:
1. explicit authority boundaries
2. deterministic execution flow
3. contract-governed decision seams
4. replayable execution evidence
5. bounded model influence

AI systems evolve rapidly. Runtime stability must hold as model behavior changes.

## 2. Core Principles

Orket is governed by five architectural principles:
1. deterministic runtime
2. explicit authority
3. volatile strategy isolation
4. runtime truth
5. replayability

## 3. Runtime Model

The runtime can be described as:

```text
deterministic_runtime =
    pure_compute
    + explicit_inputs
    + declared_side_effects
```

More concretely:

```text
next_state =
    deterministic_transition(current_state, input_event)
```

Decision nodes influence strategy, but only deterministic runtime logic performs state transitions.

## 4. System Structure

The runtime is organized into five layers:

```text
interfaces
   v
application  <- authority
   v
core         <- rules + contracts

decision_nodes   <- strategy
adapters         <- integrations
```

Conceptually:

```text
deterministic runtime kernel
+ strategy plugins
+ integration adapters
```

## 5. Runtime Layers

### `core`

Defines stable domain primitives:
1. vocabulary
2. invariants
3. contracts
4. schema definitions

Core must remain deterministic and dependency-minimal.

Core must not depend on:
1. application
2. adapters
3. interfaces

### `application`

Authoritative runtime coordination.

Responsibilities:
1. orchestration flows
2. state transitions
3. persistence coordination
4. side-effect authorization
5. degraded execution handling
6. observability sequencing

Application services own runtime truth.

### `adapters`

Integration boundaries for external systems, including:
1. LLM providers
2. storage systems
3. VCS
4. tools
5. external APIs

Adapters translate between external semantics and Orket contracts.
Adapters do not define policy or runtime authority.

### `interfaces`

Transport edges for user and external interaction, including:
1. CLI
2. API
3. UI surfaces

Interfaces translate external requests into application contracts.

### `decision_nodes`

Volatile strategy surfaces, including:
1. planning
2. routing
3. model selection
4. evaluation strategy
5. tool strategy

Decision nodes influence strategy but must not control execution truth.

## 6. Authority Model

Authority is strictly defined:

| Layer | Authority |
| --- | --- |
| `core` | vocabulary, invariants, contracts |
| `application` | runtime flow, state transitions, persistence |
| `adapters` | external system translation |
| `interfaces` | request/response shaping |
| `decision_nodes` | strategy recommendations |

Decision nodes never define runtime truth.

## 7. Dependency Direction

Dependencies must follow this direction:
1. `interfaces -> application`
2. `application -> core`
3. `application -> adapters`
4. `application -> decision_nodes`
5. `adapters -> core`
6. `decision_nodes -> core contracts`

Disallowed:
1. `core -> application`
2. `core -> adapters`
3. `core -> interfaces`
4. `adapters -> application`
5. `decision_nodes -> interfaces`
6. `decision_nodes -> persistence`

Dependencies must not be bypassed via dynamic imports or runtime reflection.

## 8. Decision Node Rules

Decision nodes behave as bounded decision functions:

```text
decision = f(explicit_inputs)
```

Decision nodes must:
1. receive structured inputs
2. return structured outputs
3. remain stateless across invocations

Decision nodes must not:
1. mutate runtime state
2. write files or databases
3. execute tools
4. create artifacts
5. emit user-visible output
6. read mutable runtime state
7. inspect runtime databases
8. access filesystem state for decision context
9. maintain hidden state between invocations

Decision nodes may invoke adapters only if those adapters are side-effect free.
Decision nodes may recommend strategies but must not produce instructions executable without application-layer interpretation.

## 9. Explicit Input Requirement

Decision nodes must receive all required context through structured input contracts.

The application orchestrator is responsible for collecting context and invoking decision nodes:

```text
application_service
      v
collect inputs
      v
invoke decision_node(inputs)
```

Decision nodes must never reach into runtime environment state for missing context.

## 10. Deterministic Runtime Boundary

Deterministic execution includes all runtime logic outside decision nodes and external integrations:

```text
deterministic_runtime =
    application
    + core
```

Only these may introduce nondeterminism:
1. decision nodes
2. external integrations

## 11. Time and Randomness

Time and randomness introduce nondeterminism and must be treated as explicit inputs.

Disallowed inside deterministic runtime:
1. `time.time()`
2. `datetime.now()`
3. `uuid4()`
4. `random.*`

If required, time/random values must be supplied by orchestrator input contracts.

## 12. Stateless Decision Nodes

Decision nodes must be stateless across invocations.

Disallowed patterns:
1. module-level caches
2. mutable globals
3. singleton memory
4. hidden runtime inspection

Otherwise decisions become:

```text
decision = f(inputs, hidden_state)
```

That breaks replayability and auditability.

## 13. Side-Effect Ownership

Only application services may authorize durable side effects, including:
1. database writes
2. filesystem writes
3. artifact creation
4. tool execution
5. external API calls

Adapters execute side effects but do not decide them.
Decision nodes must never cause side effects.

## 14. Adapter Side-Effect Classification

Adapters must declare side-effect class:

```text
side_effecting = true | false
```

Rules:

| Caller | Allowed adapter type |
| --- | --- |
| `decision_nodes` | `side_effecting = false` |
| `application_services` | both |

This prevents architecture drift via implicit side effects.

## 15. Runtime Truth Rule

The system must never claim an operation occurred unless corresponding state effect occurred.

Logs, events, and user-visible messages must not claim success unless:
1. state change was verified, or
2. result is explicitly marked advisory.

Narrated success without state effect is a defect.

## 16. Result Vocabulary

Result states should remain stable and canonical:
1. `success`
2. `failed`
3. `blocked`
4. `degraded`
5. `advisory`

States must be mutually exclusive.
`success` must imply verified state effect.

## 17. Observability Identity

Target-state observability events should include:
1. `run_id`
2. `trace_id`
3. `timestamp`
4. `event_type`
5. `origin_layer`
6. `component`
7. `result`

Migration note:
1. Current canonical event schema remains `docs/architecture/event_taxonomy.md`.
2. Any move to this identity model must be versioned and accompanied by taxonomy updates.

## 18. Observability Ordering

Events must be emitted only after state transitions are verified.

Correct pattern:

```text
perform operation
v
verify state change
v
emit event
```

Incorrect pattern:

```text
emit event
v
attempt operation
```

Event streams must represent verified state history, not attempted intent.

## 19. Replay Principle

Critical operations should produce replayable artifacts.

Replay artifacts should include:
1. input snapshot
2. resolved policy
3. decision outputs
4. contract versions
5. configuration inputs

Replay execution must not mutate durable state.

## 20. Durable vs Volatile State

Durable runtime state resides under:
1. `.orket/durable/`

Workspace execution artifacts reside under:
1. `workspace/`

Current durable defaults (still authoritative while transitioning):
1. runtime DB: `.orket/durable/db/orket_persistence.db`
2. webhook DB: `.orket/durable/db/webhook.db`
3. live-loop DB: `.orket/durable/observability/live_acceptance_loop.db`
4. user settings: `.orket/durable/config/user_settings.json`
5. gitea export cache/staging: `.orket/durable/gitea_artifacts/`

Durable state represents retained operational truth.
Workspace artifacts may be sanitized/discarded per contract.

## 21. Architectural Invariants

The architecture enforces five critical invariants:

| Invariant | Prevents |
| --- | --- |
| side effects only in application authority | uncontrolled mutation |
| decision nodes cannot mutate state | AI volatility leaking into runtime truth |
| deterministic runtime outside decisions | replay divergence |
| runtime truth tied to verified state change | hallucinated success |
| standardized observability identity and ordering | debugging ambiguity |

These invariants reinforce each other and make incorrect designs harder to implement.

## 22. Simplicity Rule

Favor the simplest design that preserves:
1. explicit authority
2. deterministic execution
3. bounded volatility
4. replayable evidence

Additional abstraction is allowed only when it improves those properties.

## 23. Summary

Orket is a deterministic runtime with bounded volatile strategy seams.

The architecture ensures:
1. AI influences strategy but does not control execution truth
2. runtime state transitions remain deterministic
3. side effects occur only through authorized layers
4. system behavior remains replayable and auditable

Runtime executes deterministically.
Strategy modules provide bounded guidance.

## 24. Transitional Current-State Specifics

### Gitea artifact export local staging

`.orket/durable/gitea_artifacts/` is local staging/cache for export payloads and a local git mirror used by the exporter.
It is not the Gitea server's own storage location.

### ReviewRun primitive (v0)

Orket includes a manual `ReviewRun` primitive in `orket/application/review/`.

Current `ReviewRun` properties:
1. snapshot-first input contract (`ReviewSnapshot`)
2. deterministic policy resolution with canonical digesting
3. deterministic review lane is authoritative
4. model-assisted lane is optional and advisory-only
5. replay is offline and artifact-driven (`snapshot.json` + `policy_resolved.json`)

`ReviewRun` is deliberately not a webhook or auto-trigger pipeline in v0.

