# Orket Architecture (Target State)

Last updated: 2026-09-18
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
4. `docs/specs/RUNTIME_PROJECT_ROOTS.md`: operator project state comes from the
   selected invocation/application root, while immutable runtime assets remain
   package-owned. `docs/specs/RUNTIME_STORE_BINDING.md` owns runtime-store binding
   and explicit offline migration of historical relative epic scopes.

## Known Current Exceptions

As of 2026-07-30, these divergences are known and accepted as transition debt:

The owner, reason, status, evidence, and removal condition for current exceptions
are tracked in
`docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json`. That
register also records review-discovered ship-risk and self-deception debt that is
not accepted as target-architecture conformance.

1. Dependency layering exceptions:
   1. `orket/interfaces/coordinator_api.py` and `orket/interfaces/orket_bundle_cli.py` import core/domain types directly.
2. Decision-node purity exceptions:
   1. `orket/decision_nodes/builtins.py` still retains mutable planning/routing context. Loop limits now consume immutable explicit values; application owns registry selection, executable tool bindings, provider construction and organization overrides. API authentication, observed paths, board loading and calendar inputs now belong to application services; API strategy retains request/presentation recommendations. API/engine/pipeline construction, env bootstrap, and session-id minting on the touched runtime paths also live in explicit services.
3. API runtime composition:
   1. `create_api_app()` returns a distinct FastAPI app with an application-owned `ApiRuntimeContainer`, runtime state, host, engine, decision node, outbound-policy snapshot, stream/interaction/extension owners, outward stores/services, and tracked task teardown. Pure ASGI middleware admits each HTTP/WebSocket invocation through the container, retaining ownership through streaming and awaited connectors. Shutdown waits for active invocation cleanup before resources and engine; availability and remaining lifetime limits live in `docs/specs/API_RUNTIME_LIFECYCLE.md`.
   2. `orket/interfaces/api.py` is import-pure with respect to FastAPI/runtime owners: it exports no module-default app or mutable owner aliases and constructs no application, adapter, decision-node, kernel, or orchestration implementation. Production callers use `orket.runtime.create_api_app(...)` and retain the returned app.
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

Governed-agent shared invocation/broker ports and wake/schedule/webhook records
reside in `orket/core/contracts/`. Concrete authority-guard invocation remains in
application; storage adapters implement the shared core ports. Migration and
manual wake command ownership are documented in
`docs/architecture/CONTRACT_DELTA_AGENT_CONTRACTS_C_2026-09-16.md`.

Current D1 boundaries implement this separation for failure report construction,
structural reconciliation plans and ToolGate policy over explicit file facts.
Application services own publication, traversal, storage and AST/iDesign workers;
adapters receive validation authority through a core protocol. Migration and
current proof limits are in
`docs/architecture/CONTRACT_DELTA_CORE_EFFECT_BOUNDARIES_D_2026-09-14.md`.
This is not whole-core purity or C/D acceptance.

The orchestrator's supplied control-plane clock covers both issue dispatch and
scheduler namespace publication, including activation-failure cleanup. Direct
composition retains the UTC adapter default. The clock wiring does not make the
scheduler's multi-publication closeout atomic; migration and limits are recorded in
`docs/architecture/CONTRACT_DELTA_SCHEDULER_CLOCK_D_2026-09-17.md`.

Bug-fix phase core values likewise consume explicit time. Application owns their
manager, cache, verified persistence and event workers. Migration and limits:
`docs/architecture/CONTRACT_DELTA_BUG_FIX_PHASE_D_2026-09-16.md`.

Protocol hashing, invocation records and result/error vocabulary live in core.
Storage adapters own operation-commit persistence and receipt files. Protocol
repository file workers retain lifetime ownership through interruption; callers'
nested receipt/event/summary inputs are captured before the first await.
Migration and scoped limits:
`docs/architecture/CONTRACT_DELTA_PROTOCOL_LEDGER_CD_2026-09-17.md`.

Dual-ledger lifecycle and recovery authority belong to application services.
Storage owns bound, verified intent files and native admission; core validates
intent and observed backend content. Migration and current proof limits:
`docs/architecture/CONTRACT_DELTA_DUAL_LEDGER_CD_2026-09-17.md`.

Application also owns governed native invocation admission, launch and cleanup.
Cancellation retains the admitted process transition; pending/duplicate owners
cannot report unobserved teardown. Candidate limits and migration:
`docs/architecture/CONTRACT_DELTA_AGENT_INVOCATION_LIFETIME_D_2026-09-17.md`.

Protocol run-graph reconstruction likewise lives in core over captured JSON
inputs. Storage performs owned ledger replay and verified graph publication after
observed terminal append; a matching terminal retry repairs its projection.
Migration and limits:
`docs/architecture/CONTRACT_DELTA_PROTOCOL_GRAPH_CD_2026-09-17.md`.

Provider identity/defaults and captured target values are core contracts. Application
preparation captures settings before awaiting and owns inventory/load worker lifetime;
load readiness requires a post-load observation. Client settings capture and remaining
composition limits are in
`docs/architecture/CONTRACT_DELTA_PROVIDER_INPUTS_CD_2026-09-17.md`.

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

SDK memory coordination likewise belongs to application. The public synchronous
memory write captures nested request metadata before bridge submission; scope,
control and policy semantics retain their existing authorities. Migration and
remaining shared-bridge/store limits:
`docs/architecture/CONTRACT_DELTA_SDK_MEMORY_OWNER_CD_2026-09-18.md`.

The shared SQLite adapter verifies WAL mode before yielding a connection. Its
bounded busy-family retry applies only to admission, closing failed connections
before another attempt; caller statements and commits are not replayed.

Tool-result publication captures nested input values and retains each admitted
file worker through cancellation. Protocol receipts, ordinary replay files and
control-plane step publication remain separate effects; an interrupted publication
cannot authorize redispatch merely because a file exists. Ownership and migration:
`docs/architecture/CONTRACT_DELTA_TOOL_RESULT_WORKERS_D_2026-09-17.md`.

Extension scaffolding follows that ownership: application selects the command,
storage drains materialization and verifies files, and both source and installed
callers consume package-owned archives. Canonical authoring sources and the
mechanical archive check are documented in
`docs/architecture/CONTRACT_DELTA_EXTENSION_SCAFFOLD_PACKAGING_D_2026-09-17.md`.

API authentication uses an application-owned settings snapshot shared by HTTP,
WebSocket and startup security checks. Explorer/metrics workers and rooted board
reads are application-owned; pure EOS calculation consumes captured baseline and
explicit time. Migration and remaining composition/lifetime work:
`docs/architecture/CONTRACT_DELTA_API_AUTHORITY_INPUTS_CD_2026-09-17.md`.

Governed-agent CLI submission, inspection/replay and operator controls delegate
to application command services. Submission captures immutable options and owns
catalog/request preparation and provider cleanup through interruption. Public
arguments and result schemas are unchanged; migration and limits are in
`docs/architecture/CONTRACT_DELTA_AGENT_COMMANDS_C_2026-09-16.md`.

### `adapters`

Integration boundaries for external systems, including:
1. LLM providers
2. storage systems
3. VCS
4. tools
5. external APIs

Adapters translate between external semantics and Orket contracts.
Adapters do not define policy or runtime authority.

Provider preparation follows that boundary through the core
`ProviderPreparationPort`. Application owns captured discovery/load policy; the
LLM adapter binds an admitted target to the same provider, model request and
endpoint before inference, regardless of the HTTP client type. Pure endpoint
normalization lives in core. Migration and remaining concurrency/native CLI
limits: `docs/architecture/CONTRACT_DELTA_PROVIDER_PREPARATION_CD_2026-09-18.md`.

`LocalPromptingService` in `orket/application/services/local_prompting_service.py`
owns prompt policy. `create_local_model_provider` captures environment and injects
that authority through the core `LocalPromptingPort`; raw provider construction
requires the port. The SDK model owner lives in
`orket/application/services/sdk_llm_provider.py`. Request messages and nested context
are copied before provider preparation can await. The registry worker is retained
through cancellation; parsing and provenance use the same observed bytes, with no
shared mutable registry cache. Policy values are immutable; transport and telemetry
exports are detached. The packaged registry location and profile semantics are
unchanged. Migration and remaining scope:
`docs/architecture/CONTRACT_DELTA_PROMPT_POLICY_CD_2026-09-17.md`.


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

Decision-node registry construction lives in
`orket/application/services/decision_node_registry.py` and captures selection settings
once. Tool strategies return immutable tuples of known names; application composition
alone binds executable tools. `ModelClientFactory` owns provider/client construction
over captured settings. Loop limits consume `LoopPolicyInputs`; `ConfigLoader` applies
captured organization overrides without a strategy mutation callback. Migration,
retired configuration and remaining prompt/settings/async limitations are in
`docs/architecture/CONTRACT_DELTA_DECISION_INPUTS_CD_2026-09-17.md`.


`ModelSelectionService` captures selection environment and caller configuration,
owns settings/score preparation, and returns immutable decisions. Prompt strategies
receive `ModelSelectionInput`; application applies advisory compliance policy.
Configured score reports retain status and a digest of the observed bytes.
Preview coordination lives in `orket/application/services/preview_service.py`;
the API host owns asynchronous preview/driver bootstrap and request-driver cleanup.
Retired imports, default-settings scope and current verification limits:
`docs/architecture/CONTRACT_DELTA_MODEL_SELECTION_CD_2026-09-17.md`.

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

The executable authority is `model/core/contracts/dependency_direction_policy.json`
(v2). Runtime, orchestration, kernel, services, extension admission and other
coordination packages map to application; CLI/API edges map to interfaces. Domain
vocabulary, schemas and exceptions map to core. Filesystem, clock, logging and
other external implementations map to adapters. Exact prefix classifications and
conditional decision-node targets are generated into
`docs/architecture/dependency_graph_snapshot.md` from that policy. Classification
does not itself establish pure core behavior or adapter side-effect safety.

`python scripts/governance/check_dependency_direction.py` rejects unknown
classifications, unpermitted edges, unresolved import/reflection routes and
cross-layer strongly connected components. Git-visible inventory, source bytes
and Python encodings define the observation; read/parse/discovery errors cannot
produce a passing verdict. The graph exporter reports observation separately from
the verdict. These are static dependency checks, not a runtime call graph.

Only exact source/target exceptions with owner, reason, introduction and removal
metadata can waive an edge; expiry and unused exceptions fail closed. They cannot
waive analysis errors or authority cycles. The architectural exception register
is an area-level debt inventory and does not grant dependency exemptions. Existing
repository failures remain C/D work; the v2 cutover is not repository conformance
acceptance. ADR-0001's platform tier and legacy budget are superseded.

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
5. gitea export cache/staging: `.orket/durable/gitea_artifacts/`; retains local
   payload/Git objects for the intent contract in `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`.
6. epic publication journal: `<runtime_db>.epic-publications.sqlite3`, beside the
   selected runtime DB; retains run/resource admissions with initialization markers
   and owner-recovery history, unfinished approval pauses, workload outcomes,
   approval recovery history, preparation inputs, export-attempt state with bound local owners/recovery history, and
   verified publication progress across standard runtime restart. Preserve it with
   the other retained runtime, control-plane and acceptance evidence stores.
   `<publication-journal>.continuations/<sha256-session-id>.lock` files retain
   native continuation ownership identities beside that journal. Preserve these
   files with claimed pauses; deleting/replacing them cannot authorize recovery.
   Ownership covers approval continuation through durable outcome/next-pause
   retention; the continuing caller releases it before export and publication.
   Other callers can independently finalize a retained outcome.
7. card acceptance evidence: `.orket/durable/db/orket_persistence.db.card_acceptance.sqlite3`;
   standard runtime composition places it beside a custom card database using
   `<runtime-db-filename>.card_acceptance.sqlite3`.
8. control-plane evidence: `control_plane_records.sqlite3` beside the selected
   runtime DB. Runtime composition resolves the runtime path once against the
   invocation directory, including a relative `ORKET_DURABLE_ROOT`; engine, epic
   and governed turn composition share `control_plane_db_for_runtime`. Workspace
   changes cannot select another control-plane store. Historical relative epic
   scopes require the explicit offline binding in `docs/specs/RUNTIME_STORE_BINDING.md`.
   Governed turn execution uses native ownership files at
   `<control-plane-db>.turn-owners/<sha256-run-id>.lock`. Preserve these beside the
   store; replacing a live file cannot establish ownership. Retained dispatch
   markers and their uncertainty contract live in
   `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.
   It preserves runtime/journal/artifact/native-lock paths and copies one checked
   old control-plane store without merging unrelated histories. Family authority and
   scoped conformance are recorded in `CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`;
   storage migration does not expand those guarantees.

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
