# Orket Architecture (Target State)

Last updated: 2026-09-21
Status: Active target architecture (transitioning)

Canonical architecture specification for the Orket runtime.

This document defines architectural constraints governing runtime behavior and component responsibilities.
Rules in this document are normative for target-state architecture and for new/modified paths unless a listed transition exception applies.

The architecture is intentionally minimal. Each rule exists to prevent a real systemic failure mode.

Core package data retains authored resource bytes in wheels and source archives.
The permission example/schema and ODR artifact schema are explicitly shipped;
availability does not activate runtime policy or completion-verifier authority.
Contract: `docs/architecture/CONTRACT_DELTA_PACKAGE_DATA_C_2026-09-21.md`.

Run-start bootstrap retains its worker through interruption; side-effecting storage
owns bounded native directory publication. Retry timing does not replace captured
run time. The concrete refusal and partial-effect limits live in
`docs/architecture/CONTRACT_DELTA_RUN_START_PUBLICATION_D_2026-09-19.md`.

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
   1. Dependency analysis recognizes six bounded extension-loading/import-interception routes by inspecting their guards, bindings and forwarding bodies. Unknown routes still fail. Current source/installed acceptance belongs to the architectural-truth plan; core purity and runtime ownership remain separate C/D obligations.
2. Decision-node purity exceptions:
   1. `orket/decision_nodes/builtins.py` still retains mutable planning/routing context. Loop limits now consume immutable explicit values; application owns registry selection, executable tool bindings, provider construction and organization overrides. API authentication, observed paths, board loading and calendar inputs now belong to application services; API strategy retains request/presentation recommendations. API/engine/pipeline construction, env bootstrap, and session-id minting on the touched runtime paths also live in explicit services.
3. API runtime composition:
   1. `create_api_app()` returns a distinct FastAPI transport with captured construction inputs. Its lifespan acquires the application-owned `ApiRuntimeContainer`, runtime state, host, engine, decision node, outbound-policy snapshot, stream/interaction/extension owners and outward stores/services through an owned preparation worker. HTTP/WebSocket admission requires completed initialization and retains ownership through streaming and awaited connectors. Shutdown waits for active invocation cleanup before resources and engine. The 0.6.39 construction transition and its scoped source/installed verification limits live in `docs/specs/API_RUNTIME_LIFECYCLE.md` and the canonical architectural-truth plan.
   2. `orket/interfaces/api.py` is import-pure with respect to FastAPI/runtime owners: it exports no module-default app or mutable owner aliases and constructs no application, adapter, decision-node, kernel, or orchestration implementation. Production callers use `orket.interfaces.runtime_entrypoints.create_api_app(...)` and retain the returned app.
4. Deterministic runtime clock/input exceptions:
   1. Some application paths still use wall-clock helpers directly (for example `time.time()` / `datetime.now(...)`) instead of injected runtime inputs.
   2. Direct extension-manager and control-plane construction now refuse event-loop threads; application preparation owns their workers and captures locations. The synchronous control-plane builder binds relative database paths at construction. Broader async reachability remains open; the 0.6.40 migration and partial-effect limits are in `docs/architecture/CONTRACT_DELTA_DIRECT_EXTENSION_CONSTRUCTION_D_2026-09-20.md`.
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

Bundle commands enter application `BundleService`; the side-effecting storage
adapter retains archive/file workers through cancellation. Packing checks admitted
manifest agreement and required members, verifies a temporary archive, replaces
and verifies the destination before success. Core manifest validation consumes
supplied payloads. Offline ledger verification and CLI connector registry
composition also enter application. Migration and interruption/publication limits:
`docs/architecture/CONTRACT_DELTA_BUNDLE_AUTHORITY_CD_2026-09-18.md`.

`ExecutionTurn` requires an explicit timestamp or explicit absence; constructing
a core turn never reads the host clock. Application `Agent` supplies captured
clock authority. Existing replay/resume snapshots lack original response times,
so reconstructed turns carry `None`. Migration and remaining clock scope:
`docs/architecture/CONTRACT_DELTA_TURN_TIME_D_2026-09-18.md`.

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

Sandbox HTTP verification follows the same boundary: core captures explicit
scenario/target/time values and compares observations; application owns HTTP
dispatch, client cleanup and result adoption. Fixture subprocess support code
resides in the execution adapter. Exact comparison and migration semantics are in
`docs/specs/SANDBOX_HTTP_VERIFICATION.md`. Sandbox creation timestamps and schema
identities are explicit core inputs. Authored configuration obtains missing IDs
through the application service; environment extras fail without warning effects.
Contract: `docs/specs/SCHEMA_INPUT_OWNERSHIP.md`. Remaining effects, decision context,
adapter classification and async reachability still require D acceptance.

The runtime CLI captures engine inputs after startup and owns engine construction
through interruption. Board/replay reads, manifest output and native path
resolution retain their workers; a completed untransferred engine is closed.
Argument declarations remain one authority in `orket/interfaces/cli_arguments.py`.
CLI inspection contract (subsequent API and driver contracts are specified below):
`docs/architecture/CONTRACT_DELTA_CLI_RUNTIME_OWNERSHIP_D_2026-09-21.md`.

API run queries own log, token, replay-list and graph observation workers;
targeted replay shares the CLI's owned inspection service. Pure record projections
preserve response semantics and diagnostic meaning. Captured roots constrain
resolved log/artifact paths; invalid paths map to HTTP 400. This is bounded path
checking, not hostile-race containment or CAP-2 isolation. Contract and limits:
`docs/architecture/CONTRACT_DELTA_API_RUN_OBSERVATION_D_2026-09-21.md`.

Legacy extension actions capture plan/bootstrap inputs and use an owned engine
context that closes before returning. Direct synchronous adapter construction
refuses an event-loop thread; interrupted workloads without confirmed terminal
evidence retain their existing unresolved control-plane state. Migration and scope:
`docs/architecture/CONTRACT_DELTA_LEGACY_ACTION_ENGINE_D_2026-09-21.md`.

Synchronous ConfigLoader methods refuse event-loop calls and close unstarted
coroutines. Async engine/pipeline embeddings use their `.open(...)` contexts
for captured bootstrap/path inputs, worker construction and required cleanup.
Direct engine, pipeline and runtime-context construction is pre-loop/worker
only. Existing action/result authority is retained. Migration and limits:
`docs/architecture/CONTRACT_DELTA_CONFIG_SYNC_BRIDGE_D_2026-09-21.md`.

Runtime cleanup attempts every declared resource after an earlier close failure.
Synchronous close ports use owned workers; admitted cleanup remains owned
through repeated cancellation. Multiple failures remain visible in exception
groups, and failed cleanup cannot set the engine/pipeline closed flag. Port
migration, failure handling and proof limits:
`docs/architecture/CONTRACT_DELTA_RUNTIME_RESOURCE_CLEANUP_D_2026-09-21.md`.

Async file operations own native path/file work through interruption and capture
standard path/reference values and serialized write content. Filesystem tools
retain the admitted mutation authority and existing path locks; authorized
connector dispatch keeps its bound-filesystem authority. Migration, native
current-directory observation and containment limits:
`docs/architecture/CONTRACT_DELTA_ASYNC_FILE_OPERATIONS_D_2026-09-21.md`.

Sandbox log requests capture invocation inputs before owned pipeline construction,
retain native reads through interruption and close each ephemeral pipeline before
return. Nonzero log-command exits are visible failures; the ten-second command
timeout is unchanged. Direct sync log reads refuse an event-loop thread. Contract,
async embedding migration and remaining ownership limits:
`docs/architecture/CONTRACT_DELTA_API_SANDBOX_LOGS_D_2026-09-21.md`.

Driver async creation captures root, environment and settings before owned
construction; direct synchronous construction refuses an event-loop thread.
API chat and interactive CLI use shared runtime owners. Console reads settle
before interrupted return; normal EOF cannot erase pending cancellation.
Provider close gates CLI exits and remains owned through repeated interruption.
Contract, embedding migration and blocking-input limit:
`docs/architecture/CONTRACT_DELTA_DRIVER_LIFETIME_D_2026-09-21.md`.

Driver model-context preparation captures project/model roots and environment
before owned configuration and inventory work. Interruption retains native reads;
worker failures and missing roots remain visible before provider dispatch.
Constructor and request config loaders consume the same captured environment,
including explicit empty inputs. Contract and remaining constructor/CLI scope:
`docs/architecture/CONTRACT_DELTA_DRIVER_INVENTORY_D_2026-09-21.md`.

Organization-loop async creation captures settings, root and environment before
owned configuration loading. Scans and card construction remain owned through
interruption; required cleanup gates caller completion. The canonical CLI loop
uses that factory. Discovery uses the captured project root and orders normalized
numeric priority after critical-path weight. Contract:
`docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`.

The public orchestration helper and collection-member supervisor own runtime
construction and close through interruption. Prepared child factories retain
selected parent inputs; runtime composition passes its snapshot to subordinate
factories. Async runtime settings capture honors bound settings/preferences
independently and owns selected persistence reads. Direct synchronous constructors
remain separate work. Contracts: `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`
and `docs/specs/SETTINGS_INPUT_OWNERSHIP.md`.

Agent configuration and turn preparation's sync-only asset loading use owned
workers. Cancellation and timeout retain the admitted work through settlement;
worker failure remains visible. Available async asset loaders are invoked once,
and their TypeError is not retried through another loader. Synchronous public
configuration bridges remain separate work: `docs/specs/REMAINING_RUNTIME_INPUTS.md`.

Async kernel invocations retain request targets and operator values before
calling the kernel or awaiting publication. Direct control-plane publishers also
capture request, response and ledger JSON before their first await, preventing
borrowed mutations from changing snapshots or terminal claims. Stable JSON and
existing durability/transaction limits remain: `docs/specs/KERNEL_PUBLICATION_INPUTS.md`.

Kernel proposal admission selects immutable operator enablement/resolver flags
before request validation or hashing. Trusted Python callers may supply the typed
input; request and HTTP payload fields cannot supply it. Default calls observe
the current environment per invocation. Existing decision, approval, digest and
in-memory ledger limits remain: `docs/specs/KERNEL_POLICY_INPUTS.md`.

Gitea loop owners capture environment, limit rules and roots before awaits;
pipeline entry also supplies its selected clocks and control-plane database.
Construction, summary I/O and acquired HTTP clients remain owned through
interruption. Claim-failure publication uses the selected UTC provider; reservation
rollback refuses reversed observations without clamping. Explicit remote lease
timestamps and unresolved runtime authority remain retained. Contract and limits:
`docs/specs/GITEA_LOOP_INPUTS_AND_LIFETIME.md`.

Cards, manual-review and trusted extension owners retain their selected UTC
callable through transaction-scoped publication. Pipeline and extension-manager
clocks reach those owners; terminal retries retain published timestamps, and
clock failure cannot fabricate final success. Defaults retain host UTC behavior.
Contract and limits: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

Agent construction captures model-family configuration; journal publication uses
the selected clock or captured caller timestamp. Epic setup calculates one sprint
from its selected time, immutable baseline and captured configured timezone
before asset reads. Timezone lookup has an owned worker; v0.6.53 corrects the
v0.6.52 host-timezone regression. Contracts and scope limits:
`docs/specs/REMAINING_RUNTIME_INPUTS.md`.

Execution setup and collection entry capture session/build identifiers before
asset reads. Custom build selectors receive a sanitized string value; selected
identities must be nonempty plain strings. Existing durable admission and child
authority remain governed by `docs/specs/EXECUTION_IDENTITY_INPUTS.md`.

API strategies receive immutable metrics, explorer, preview, archive and error
facts. Application captures invocation recommendations before intervening awaits
and refuses archive response claims that contradict observed results. Earlier
archive commits remain durable on later refusal. Input migration and boundaries:
`docs/specs/API_STRATEGY_INPUTS.md`.

Sandbox policy input ownership, strict recommendation admission and partial-effect
limits live in `docs/specs/SANDBOX_POLICY_INPUTS.md`. Creation captures its selected
policy and fresh secrets before preflight; strategies receive immutable port and
compose facts. Early refusal releases its allocation; later refusal retains
existing durable reconciliation evidence.

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

Controller runtime hooks capture policy and invocation roots before dispatch.
Dispatch prepares its own manager through the retained application worker;
disabled controllers do not construct one. Direct dispatchers require an explicit
manager. CLI preparation also captures environment/cwd before worker scheduling.
Migration, partial directory effects and remaining synchronous construction scope:
`docs/architecture/CONTRACT_DELTA_CONTROLLER_CONSTRUCTION_D_2026-09-19.md`.

Extension installation admits a distinct checkout before locked, verified catalog
publication; failed upgrades retain prior installations. Native Git commands and
catalog/preflight workers remain owned through interruption. Manager inputs and
policy are captured before preflight, and controller SDK admission uses that same
catalog observation. Async installation migration, native ownership paths and
remaining construction/publication limits:
`docs/architecture/CONTRACT_DELTA_EXTENSION_INSTALL_D_2026-09-19.md`.

Owned ACTIVE sandbox health retries publish any missing deployment effect before
returning success, after lease/resource publication with one captured timestamp.
Existing lease monotonicity guards remain active. Recovery and partial-effect limits:
`docs/architecture/CONTRACT_DELTA_SANDBOX_DEPLOY_RECOVERY_D_2026-09-19.md`.

Application retains SDK and legacy artifact/provenance workers through interruption,
captures caller inputs before awaiting and preserves confirmed execution outcomes
when later projection publication fails. Storage verifies each published JSON file;
interaction lifecycle completion stays with the interaction owner. Contract and
publication/concurrency limits: `docs/architecture/CONTRACT_DELTA_WORKLOAD_PUBLICATION_D_2026-09-19.md`.
Application also captures one immutable workload policy per invocation for
admission, artifact limits, result identity and provenance redaction. Captured
fields, Git observation ownership and remaining input scope:
`docs/architecture/CONTRACT_DELTA_WORKLOAD_POLICY_D_2026-09-19.md`.

SDK process supervision reuses the native command owner; side-effecting storage
owns private request/result files. Application retains admitted workers and
propagates uncertainty without inventing a terminal no-effect receipt. Lifetime,
deadline and recovery limits: `docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md`.
Controller schema reads use a read-only storage adapter and a package-owned
canonical asset. Application captures validation inputs and retains the read
worker; explicit paths never share a first-reader schema cache. Contract:
`docs/architecture/CONTRACT_DELTA_CONTROLLER_SCHEMA_CD_2026-09-19.md`.

Extension entrypoint adoption uses a shared side-effecting source-origin adapter.
Application retains legacy registration and SDK validation workers through
interruption. Selected module/package identity checks do not establish transitive
import provenance or hostile-code containment. Migration and remaining lifetime
scope: `docs/architecture/CONTRACT_DELTA_EXTENSION_ORIGINS_CD_2026-09-19.md`.

Protocol inspection follows that ownership: CLI and HTTP delegate to application
query services that capture requested inputs and retain filesystem/query cleanup
through cancellation. Core compares explicit snapshots with event evidence
admission; application campaigns preserve the comparator's baseline verdict.
Path scope, explicit CLI operands and observed-state limits are specified in
`docs/specs/PROTOCOL_QUERY_LIFETIME.md`.

`UserSettingsService` coordinates captured settings locations, verified file
publication and resumable preference migration. The public settings boundary
captures nested values before dispatch and retains file workers through
cancellation. Explicit runtime snapshots and persistence reads have separate
semantics, documented in `docs/specs/SETTINGS_INPUT_OWNERSHIP.md`; this does not
make all downstream runtime configuration immutable.

The standalone coordinator factory creates an application-owned store,
publication service and lifetime owner. Serialized admitted transitions capture
inputs and retain workers/publications through cancellation; uncertain failures
close admission and prevent a clean shutdown claim. This does not make memory
and SQLite one transaction. Its startup and limits live in
`docs/specs/COORDINATOR_RUNTIME_LIFECYCLE.md`.

Flow authoring composition and bounded run admission belong to application.
Captured definitions and host time/identity inputs feed distinct create/update
storage operations. SQLite enforces guarded saves atomically and refuses create
collisions; admitted database work retains ownership through cancellation.
Migration and interruption semantics:
`docs/architecture/CONTRACT_DELTA_FLOW_AUTHORITY_CD_2026-09-18.md`.

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

Application interaction services own admission, workload adoption, cancellation,
finalization and session close. Captured inputs and per-session transition ownership
prevent interrupted calls from stranding turns or returning unobserved commit
receipts. Storage verifies immutable commit/trace artifacts; API workloads belong
to the application lifetime. Core owns stream/context values. Migration, response
vocabulary and remaining failure limits:
`docs/architecture/CONTRACT_DELTA_INTERACTION_LIFECYCLE_CD_2026-09-19.md`.

Application owns prompt asset commands, validated interactive setup, captured
vision command inputs and operator runtime interpretation. Core owns prompt
metadata transitions over a supplied date. Prompt/setup/image publication uses
owned workers and verified file bytes; failed acknowledgement can leave effects.
The setup module entrypoint is `python -m orket.interfaces.setup_cli`.
Migration, native ownership locations and verification limits:
`docs/architecture/CONTRACT_DELTA_COMMAND_AUTHORITY_CD_2026-09-19.md`.

Application crash publication captures the selected absolute diagnostic workspace
and supplied clock. Native append/rotation ownership and closed-file readback
precede a saved-path claim; cancellation retains the worker through lock release.
Runtime CLI startup captures its invocation root, preserves fatal exit status and
reports diagnostic failure without hiding the original error. Migration and limits:
`docs/architecture/CONTRACT_DELTA_CLI_CRASH_CD_2026-09-19.md`.

Application project-vendor composition captures supplied settings and explicit
project/database locations. Local catalog workers and runtime-card operations
retain ownership through interruption; missing cards and unverified status writes
cannot return success. Unsupported vendor selections are refused. Migration,
catalog identity rules and observation limits:
`docs/architecture/CONTRACT_DELTA_PROJECT_VENDOR_CD_2026-09-19.md`.

Driver resource commands and model-proposed structural writes enter application
services that capture inputs, retain workers and share native model-file admission.
Application `ReforgerService` owns asynchronous compiler tools, retained route-input
snapshots and verified output publication; workspace-root and overlapping outputs
are refused. Migration, native lock locations and non-transactional failure limits:
`docs/architecture/CONTRACT_DELTA_DRIVER_COMMANDS_CD_2026-09-19.md`.

Interaction cancellation is admitted by application `InteractionCancellationService`.
The selected session bounds the target lookup; accepted operator actions follow
observed interruption and stream publication, with captured actor and clock.
Admitted work remains owned through interruption and audit publication. Missing
or foreign targets return 404; idle or terminal targets return 409. State, stream
and SQLite remain separate effects; audit failure does not undo interruption.
Migration and recovery limits:
`docs/architecture/CONTRACT_DELTA_INTERACTION_CANCEL_CD_2026-09-19.md`.

API hardware observations and event publication run in application-owned workers
retained through request interruption and shutdown. Events capture the selected
root and nested payload before dispatch. Extension model catalogs capture provider
settings per application and use the admitted identity in failure responses.
Migration and remaining observation limits:
`docs/architecture/CONTRACT_DELTA_API_OBSERVATIONS_CD_2026-09-19.md`.

API authentication uses an application-owned settings snapshot shared by HTTP,
WebSocket and startup security checks. Explorer/metrics workers and rooted board
reads are application-owned; pure EOS calculation consumes captured baseline and
explicit time. Migration and remaining composition/lifetime work:
`docs/architecture/CONTRACT_DELTA_API_AUTHORITY_INPUTS_CD_2026-09-17.md`.
Application also retains API initialization through close and owns event subscription
cleanup and managed broadcaster admission. Startup and failure semantics:
`docs/architecture/CONTRACT_DELTA_API_STARTUP_D_2026-09-18.md`.

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

Argument-preserving installation of a standard importer can be recognized only
from its actual unambiguous factory definition. External extension names require
an inspected validator that rejects non-plain strings, relative names and the
complete scanned namespace, with dominating local capture and no uncertain
rebinding. Builtin, factory or validator ambiguity prevents recognition. Reports
retain each proven route in `resolved_dynamic_routes`; they do not infer hidden
repository edges or exempt an arbitrary module. Runtime module-origin checks
remain independent. Scope and adversarial acceptance:
`docs/architecture/CONTRACT_DELTA_DYNAMIC_IMPORT_ANALYSIS_C_2026-09-20.md`.

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

Planner/router/evaluator calls use frozen value contracts captured by the application in
`decision_context_service`; mutable issue/team/turn models are not decision context.
The application interprets returned recommendations and retains dependency/dispatch
authority. Contract, custom-node migration and limits:
`docs/specs/DISPATCH_DECISION_INPUTS.md`.

Loop-policy admission additionally supplies captured backlog, per-seat path facts,
role tuples and guard-review values through application `loop_decision_service`.
It validates recommendations without retrying strategy failures with another
signature. A terminal-loop recommendation is not accepted build completion.

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
