# Companion True BFF-Only Migration Plan

Last updated: 2026-04-01
Status: Future implementation candidate
Owner: Orket Core
Lane type: Future migration candidate

## Authority posture

This file is not roadmap authority.
It is not an active implementation lane.
It does not reopen the archived Companion MVP lane by itself.

This file intentionally describes a future direction that conflicts with the current runtime-boundary language in `docs/specs/COMPANION_UI_MVP_CONTRACT.md`.
That contract currently says Companion runtime authority is host-owned.
This plan is a replacement candidate, not current truth.

Roadmap hold rule for this file:
1. do not copy this lane into `docs/ROADMAP.md` yet
2. do not treat this file as accepted requirements yet
3. do not imply that the contract flip has already happened

If this direction is promoted into execution, the same change that activates it must:
1. update the governing Companion contract or replace it with a successor contract
2. record the contract delta under `docs/architecture/`
3. update `CURRENT_AUTHORITY.md`, `docs/API_FRONTEND_CONTRACT.md`, and `docs/RUNBOOK.md`

## Source authorities

This future plan is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/specs/COMPANION_UI_MVP_CONTRACT.md`
5. `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/11-COMPANION-CANONICAL-IMPLEMENTATION-PLAN.md`
6. `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/00-GAP-SUMMARY-AND-DEPENDENCY-MAP.md`
7. `orket/interfaces/api.py`
8. `orket/interfaces/routers/companion.py`
9. `orket/application/services/companion_runtime_service.py`
10. `docs/templates/external_extension/src/companion_app/server.py`
11. `docs/templates/external_extension/src/companion_extension/api_client.py`
12. `orket/extensions/workload_artifacts.py`
13. `orket_extension_sdk/capabilities.py`
14. `orket_extension_sdk/llm.py`
15. `orket_extension_sdk/memory.py`
16. `orket_extension_sdk/voice.py`
17. `orket_extension_sdk/audio.py`

The archived Companion MVP material remains historical traceability input.
It is not future-lane authority for this BFF-only direction.

## Purpose

Move Companion to a true BFF-only model.

Target responsibility split:
1. Orket host owns generic extension-runtime capability execution, policy, auth, and isolation
2. the external Companion backend/BFF owns Companion product routes, product orchestration, product config semantics, and product history semantics
3. Orket core stops owning any Companion-named product API surface

This is a separation-of-authority migration, not a UI-polish lane and not an extension packaging lane.

## Non-negotiable design invariants

The future lane must preserve all of the following:
1. Orket host remains the only authority for generic capability execution and host-side side effects
2. the Companion BFF may own product semantics, but it must not import Orket internals directly
3. no hidden second runtime authority may be recreated in frontend code
4. no new Companion-named host routes may be introduced during migration
5. no opaque "invoke anything" endpoint may replace the current Companion API
6. no manifest-driven route mounting or extension route registry work belongs in this lane
7. any temporary compatibility bridge must be explicitly time-bounded and removed in the same lane

## Current truth

Companion is still special-cased in core.

Observed authority points in the repo snapshot:
1. host routes live in `orket/interfaces/routers/companion.py`
2. route mounting and Companion-specific auth branches live in `orket/interfaces/api.py`
3. `orket/interfaces/api.py` still includes `_is_companion_route`, `ORKET_COMPANION_API_KEY`, and Companion alias router mounting
4. host-owned Companion orchestration lives in `orket/application/services/companion_runtime_service.py`
5. the external gateway template in `docs/templates/external_extension/src/companion_app/server.py` is a thin proxy over Companion-specific host routes
6. the gateway host client in `docs/templates/external_extension/src/companion_extension/api_client.py` calls `/api/v1/companion/*`
7. the generic SDK capability substrate already exists in `orket_extension_sdk/capabilities.py` and `orket/extensions/workload_artifacts.py`
8. the host capability providers already expose real generic seams for:
   - `model.generate`
   - `memory.write`
   - `memory.query`
   - `speech.transcribe`
   - `voice.turn_control`
   - `tts.speak`
9. the generic SDK does not yet provide a complete substrate for all product needs:
   - `MemoryProvider` has `write()` and `query()`, but no generic clear-session operation
   - `VoiceTurnController` has `control()` and `state()`, but no protocol-level silence-delay introspection
   - `LLMProvider` has `generate()` and `is_available()`, but no model-catalog contract

The result is split authority:
1. Companion has a BFF on the extension side
2. Orket core still owns a Companion product API on the host side
3. both sides contain Companion-specific route knowledge

## End state

The target end state is:
1. no `/v1/companion/*` routes in Orket
2. no `/api/v1/companion/*` routes in Orket
3. no `_is_companion_route` branch in `orket/interfaces/api.py`
4. no `ORKET_COMPANION_API_KEY`-specific auth seam in core
5. no host-owned `CompanionRuntimeService`
6. one generic host router for extension-runtime capabilities
7. one external Companion BFF that translates product requests into generic host capability calls

The host runtime surface should be typed and capability-family specific, not one opaque execute-anything endpoint.

## Authority split target

| Concern | Future owner | Notes |
|---|---|---|
| API auth and request admission | Orket host | Generic extension-runtime auth only |
| Runtime isolation and sandbox policy | Orket host | Must remain host-owned |
| Model execution | Orket host | Through generic model transport |
| Generic memory persistence | Orket host | Host owns storage mechanics, not product policy |
| Generic STT and TTS execution | Orket host | Exposed through generic transport |
| Generic voice turn-state machine | Orket host | Product may read/control it but does not own it |
| Model-catalog introspection | Orket host | Generic operator/runtime concern |
| Capability discovery and health | Orket host | Generic operator/runtime concern |
| Companion route semantics | Companion BFF | Product API lives here |
| Prompt assembly and retrieval composition | Companion BFF | Product orchestration, not generic host logic |
| Config schema and precedence semantics | Companion BFF | Product-owned schema and merge rules |
| History shaping and retention semantics | Companion BFF | Product history is BFF-owned |
| Adaptive cadence policy | Companion BFF | Product behavior over generic voice controls |
| Degraded UX wording and fallback presentation | Companion BFF | Product-facing behavior |

## Persistence ownership target

This migration must close state ownership explicitly instead of leaving it implied.

| State family | Future authority | Allowed substrate |
|---|---|---|
| Generic session memory rows | Orket host | Generic memory write/query/clear operations |
| Generic profile memory rows | Orket host | Generic memory write/query operations |
| Companion config schema | Companion BFF | BFF store or BFF-owned serialization over generic host memory |
| Companion config precedence | Companion BFF | Must not remain host-only logic |
| Companion chat history | Companion BFF | BFF store or BFF-owned serialization over generic host memory |
| Companion product session overlays | Companion BFF | Must clear alongside BFF session clear behavior |
| Host capability availability state | Orket host | Derived from generic providers |

Acceptance rule:
1. Packet 0 must ratify the default Companion config and history storage story or record the approved exception
2. the choice must be one canonical story
3. no dual-write or ambiguous shared authority is allowed past Packet 3

## Planning defaults for activation

This future plan adopts the following defaults now so activation does not reopen basic design questions.

### Default 1 - Config and history use BFF-owned serialization over generic host memory

Default storage story:
1. Companion config and history semantics remain BFF-owned
2. the initial implementation should store those product records through generic host memory rather than introducing a second persistence backend
3. profile-scoped Companion settings serialize into generic profile memory under BFF-owned keys
4. session-scoped overlays and product history serialize into generic session memory under BFF-owned keys

Why this default:
1. it preserves BFF product authority without creating a second durable store before the generic host transport is proven
2. it keeps local-first operation simple
3. it makes migration rollback and inspection easier than a new independent BFF database

Escalation rule:
1. a separate BFF-owned store is allowed only if Packet 0 explicitly records why generic host memory is insufficient

### Default 2 - Model catalog remains a host transport surface

Default model-catalog story:
1. do not expand `LLMProvider` in Packet 1 just to force model listing into the SDK provider contract
2. expose model catalog through the host transport in Packet 2
3. revisit SDK-level model-catalog contracts only if multiple generic callers need it outside HTTP transport

Why this default:
1. model inventory is runtime introspection, not core generation behavior
2. transport-level handling is easier to verify and lower risk than widening the provider contract prematurely

### Default 3 - Silence-delay introspection remains transport metadata

Default voice-state story:
1. keep `VoiceTurnController` protocol shape minimal in Packet 1
2. return `state`, `silence_delay_sec`, `silence_delay_min_sec`, and `silence_delay_max_sec` from the host transport in Packet 2
3. only widen the protocol if non-HTTP generic callers need the extra fields

Why this default:
1. the host controller already owns the timing values
2. the BFF only needs observable metadata, not direct controller internals

### Default 4 - External Companion repo remains standalone

Default repo authority story:
1. the BFF lives in a standalone Companion repo outside this repo
2. the MVP historical local target `C:\Source\Orket-Extensions\Companion` remains the default development location unless activation explicitly supersedes it
3. this repo keeps only the template and contract-authority surface, not the product code authority

### Default 5 - Compatibility overlap is one cutover packet only

Default compatibility story:
1. old host Companion routes may coexist with the generic host transport only during Packet 3
2. Packet 4 removes the old host routes immediately after Packet 3 live proof passes
3. no second compatibility packet is allowed without an explicit roadmap-tracked exception

## Planned host transport surface

Admitted host runtime surface under the canonical future prefix `/v1/extensions/{extension_id}/runtime`:
1. `GET /capabilities`
2. `GET /models`
3. `POST /llm/generate`
4. `POST /memory/query`
5. `POST /memory/write`
6. `POST /memory/session/clear`
7. `GET /voice/state`
8. `POST /voice/control`
9. `POST /voice/transcribe`
10. `GET /tts/voices`
11. `POST /tts/synthesize`

Transport design rules:
1. use typed endpoint families, not one generic execution RPC
2. request and response bodies should align to SDK types where those types already exist
3. introspection endpoints may be transport-owned when there is no matching SDK protocol yet
4. do not leak Companion naming into path, payload, or service names

## Planned auth and security model

The future host and BFF auth posture is:
1. Orket host uses the generic host API auth path only
2. Companion-specific auth branching and Companion-specific API keys are removed in Packet 4
3. the external Companion BFF stores and presents the generic host API credential as an operator-managed secret
4. the external Companion gateway continues to enforce loopback and same-origin protections on its own product routes
5. no Companion-specific auth semantics remain in Orket core after cutover

Operational rule:
1. Packet 3 proof must exercise the BFF against the generic host auth path before Packet 4 removes the old Companion-key branch

## Planned host transport contract

These are future-lane planned payload families, not current runtime truth.

| Endpoint | Backing contract | Notes |
|---|---|---|
| `POST /llm/generate` | `orket_extension_sdk.llm.GenerateRequest/GenerateResponse` | May allow optional transport-level provider or model override fields |
| `POST /memory/query` | `orket_extension_sdk.memory.MemoryQueryRequest/MemoryQueryResponse` | Reuse existing generic memory scope vocabulary |
| `POST /memory/write` | `orket_extension_sdk.memory.MemoryWriteRequest/MemoryWriteResponse` | Reuse existing generic memory scope vocabulary |
| `POST /memory/session/clear` | New generic memory clear contract | Needed because host provider already supports it but SDK protocol does not |
| `POST /voice/control` | `orket_extension_sdk.voice.VoiceTurnControlRequest/VoiceTurnControlResponse` | Reuse existing command vocabulary |
| `GET /voice/state` | Existing `state()` plus protocol or transport metadata | Planned default keeps silence-delay values as transport metadata unless Packet 1 records an approved protocol expansion |
| `POST /voice/transcribe` | HTTP wrapper over `TranscribeRequest/TranscribeResponse` | HTTP body likely carries base64 audio rather than raw bytes |
| `GET /tts/voices` | Existing `TTSProvider.list_voices()` / `VoiceInfo` | Transport only; no new capability id required |
| `POST /tts/synthesize` | HTTP wrapper over `TTSProvider.synthesize()` | Generic response must keep degraded and unavailable semantics explicit |
| `GET /models` | New generic model-catalog contract or host transport helper | Current `LLMProvider` protocol does not expose model listing |
| `GET /capabilities` | Transport-level discovery surface | Should report capability id, availability, and degradation metadata without product shaping |

## Current-to-future file map

| Current path | Packet | Future action |
|---|---|---|
| `orket/interfaces/routers/companion.py` | 4 | retire and delete |
| `orket/application/services/companion_runtime_service.py` | 3-4 | move product orchestration out of core, then delete |
| `orket/interfaces/api.py` | 2, 4 | mount generic extension-runtime router, then remove Companion route and auth branches |
| `docs/templates/external_extension/src/companion_app/server.py` | 3 | seed reference for external BFF route migration |
| `docs/templates/external_extension/src/companion_extension/api_client.py` | 3 | seed reference for generic host transport client |
| `orket_extension_sdk/memory.py` | 1 | add generic clear-session substrate if activated |
| `orket_extension_sdk/voice.py` | 1 | keep minimal unless Packet 1 explicitly widens protocol |
| `orket_extension_sdk/llm.py` | 1 | leave generation contract stable unless Packet 1 explicitly widens model-catalog support |
| `orket/capabilities/sdk_memory_provider.py` | 1 | expose generic session-clear behavior through substrate or transport helper |
| `orket/capabilities/sdk_voice_provider.py` | 1-2 | support generic voice-state metadata exposure |
| `orket/extensions/workload_artifacts.py` | 1-2 | keep generic capability registration aligned with new transport |
| `CURRENT_AUTHORITY.md` | 0, 5 | first record authority flip, then record final operator surface |
| `docs/API_FRONTEND_CONTRACT.md` | 5 | remove host Companion routes and document generic transport |
| `docs/RUNBOOK.md` | 5 | document generic host runtime commands and BFF product routes |

## Route ownership map

| Current route | Future owner | Future behavior |
|---|---|---|
| `/api/v1/companion/status` | Companion BFF | Compose generic host capability and health introspection into product status |
| `/api/v1/companion/config` | Companion BFF | Read and write product config through BFF-owned semantics |
| `/api/v1/companion/history` | Companion BFF | Read product history from BFF-owned history store or BFF-owned serialization |
| `/api/v1/companion/chat` | Companion BFF | Orchestrate `memory.query`, `llm.generate`, and `memory.write` |
| `/api/v1/companion/session/clear-memory` | Companion BFF | Clear generic session memory and clear BFF-owned product session overlays |
| `/api/v1/companion/models` | Companion BFF | Query generic model-catalog surface |
| `/api/v1/companion/voice/state` | Companion BFF | Query generic voice-state surface |
| `/api/v1/companion/voice/control` | Companion BFF | Call generic voice-control surface |
| `/api/v1/companion/voice/transcribe` | Companion BFF | Call generic STT surface |
| `/api/v1/companion/voice/synthesize` | Companion BFF | Call generic TTS surface |
| `/api/v1/companion/voice/cadence/suggest` | Companion BFF | Product-owned logic in BFF using product config plus generic voice metadata |

## Explicit non-goals

This lane does not include:
1. extension package hardening
2. extension publish or marketplace work
3. manifest-driven host route mounting
4. public extension route registry design
5. generic frontend platform work outside the Companion BFF
6. broad session or continuity redesign beyond the needs of the Companion migration
7. "one magic endpoint" generic proxying

## Promotion gate

Do not move this plan into `docs/ROADMAP.md` until all of the following are true:
1. the contract flip away from host-owned Companion runtime authority is explicitly accepted
2. the standalone external Companion repo authority is accepted or explicitly superseded
3. the generic host runtime surface is accepted as a dedicated lane separate from extension package surface hardening
4. the missing substrate and transport seams below are accepted as in scope
5. the roadmap can point to this file or to a successor active-lane file without competing with current Companion contract authority

## Packet 0 - Contract flip and authority reset

### Purpose

Remove the current contradiction where the active Companion contract says host-owned runtime authority while the desired future model says BFF-owned product authority.

### In scope

1. define the new ownership boundary in one canonical contract
2. state that Companion product routes are BFF-owned
3. state that Orket host is generic-capability-owned
4. define which state remains host substrate versus BFF product semantics
5. define the retirement target for `/v1/companion/*` and `/api/v1/companion/*`
6. ratify the canonical storage story for Companion config and history or record the approved exception

### Out of scope

1. code movement
2. temporary compatibility routers
3. external repo implementation work

### File targets

1. `docs/specs/COMPANION_UI_MVP_CONTRACT.md` or a successor Companion BFF contract in `docs/specs/`
2. one contract-delta record under `docs/architecture/`
3. `CURRENT_AUTHORITY.md`

### Proof gate

1. contract text explicitly names the new ownership boundary
2. no active spec still claims host-owned Companion product orchestration
3. the contract delta records the ownership change, compatibility window, rollback trigger, and same-change update targets
4. config and history ownership are chosen explicitly

### Exit condition

Companion authority is no longer split across incompatible active docs.

## Packet 1 - Generic substrate completion

### Purpose

Finish the generic substrate gaps needed so the host surface can stay generic instead of reintroducing Companion-shaped seams behind a new router.

### Contract gaps to close

1. add a generic session-memory clear operation to the memory substrate because the host provider already supports it but the SDK protocol does not
2. ratify silence-delay introspection as transport-level metadata or record the approved protocol expansion
3. ratify model-catalog listing as host transport scope or record the approved provider-contract expansion

### Transport-only gaps to close

1. generic capability discovery response shape
2. generic model-catalog response shape
3. generic voice-state response shape
4. generic TTS inventory response shape

### In scope

1. generic substrate and protocol completion only
2. no Companion route or service names
3. contract tests proving substrate behavior independent of Companion code

### Out of scope

1. mounting new HTTP routes
2. BFF code changes
3. product-specific config or history semantics

### File targets

1. `orket_extension_sdk/capabilities.py`
2. `orket_extension_sdk/llm.py`
3. `orket_extension_sdk/memory.py`
4. `orket_extension_sdk/voice.py`
5. `orket_extension_sdk/audio.py`
6. `orket/extensions/workload_artifacts.py`
7. `orket/capabilities/sdk_memory_provider.py`
8. `orket/capabilities/sdk_voice_provider.py`
9. one generic provider or helper for model catalog if the current host helper cannot be reused without product leakage
10. `tests/sdk/`
11. `tests/extensions/` or `tests/application/` for generic provider parity

### Proof gate

1. contract tests prove the new substrate operations validate and preflight correctly
2. integration proof shows a workload or generic service can exercise the new operations without importing Companion code
3. no new Companion-named capability ids or protocol names are introduced

### Exit condition

The generic substrate is sufficient to express the Companion BFF needs without a Companion-specific host surface.

## Packet 2 - Generic host extension-runtime transport

### Purpose

Expose the generic capability surface through one host router and one application service that do not mention Companion.

### In scope

1. one typed extension-runtime router in `interfaces`
2. one application-owned service coordinating capability invocation and request validation
3. extension identity binding through the existing extension and workload substrate
4. generic auth and policy enforcement with no Companion-specific branches
5. explicit request and response models for each admitted endpoint family

### Out of scope

1. product-specific route names
2. manifest-driven route registration
3. compatibility aliases for new route families that still contain `companion`

### File targets

1. new `orket/interfaces/routers/extension_runtime.py`
2. new `orket/application/services/extension_runtime_service.py`
3. new request or response model module if needed under `orket/application/services/`
4. `orket/interfaces/api.py`
5. `tests/interfaces/`
6. `tests/application/`

### Guardrails

1. keep side-effect ownership in the application layer
2. do not add an opaque `invoke` endpoint
3. do not mount product routes from extension manifests in this packet
4. do not preserve Companion route names behind hidden rewrites
5. do not let the transport service import Companion code

### Proof gate

1. integration tests exercise each admitted generic endpoint family
2. live proof uses real API runtime calls with `ORKET_DISABLE_SANDBOX=1`
3. no request path in the host contains `companion`
4. architecture review records `AC-01`, `AC-05`, and `AC-10` as pass or truthful partial with legacy references only

### Exit condition

The host exposes one generic extension-runtime API surface that the Companion BFF can target directly.

## Packet 3 - External Companion BFF orchestration migration

### Purpose

Move Companion product semantics to the external BFF so the host no longer owns product-level chat, config, history, or voice workflows.

### In scope

1. BFF-owned `status`, `config`, `history`, `chat`, `clear-memory`, `models`, and `voice` routes
2. BFF-owned chat orchestration using generic host endpoints
3. BFF-owned config and history semantics
4. chosen persistence strategy for config and history
5. BFF route-level validation and request shaping
6. explicit degraded behavior when generic host capabilities are unavailable

### Out of scope

1. host compatibility shims that extend past Packet 4
2. direct imports from Orket internals
3. product logic embedded in frontend-only code

### External repo targets

Under the standalone Companion repo root:
1. `src/companion_app/server.py`
2. `src/companion_extension/api_client.py`
3. `src/companion_app/services/chat_orchestrator.py`
4. `src/companion_app/services/config_store.py`
5. `src/companion_app/services/history_store.py`
6. `tests/`

### In-repo seed references

1. `docs/templates/external_extension/src/companion_app/server.py`
2. `docs/templates/external_extension/src/companion_extension/api_client.py`

### Guardrails

1. the BFF may own product semantics, but it must not reach into Orket internals directly
2. the BFF must call only the public generic host API
3. no second hidden runtime authority may be recreated in frontend code
4. the BFF must not keep calling `/api/v1/companion/*` during or after cutover
5. the BFF must clear its own product session overlays when invoking generic session clear

### Proof gate

1. end-to-end proof shows the Companion BFF `chat` route completing through the generic host runtime surface
2. end-to-end proof covers config read or write, history retrieval, memory clear, STT, and TTS
3. degraded proof explicitly shows text-only operation when STT is unavailable
4. no BFF client code contains `/api/v1/companion/`
5. no BFF route handler imports `orket.*`
6. BFF-owned config and history records use the planning default or a documented approved exception

### Exit condition

The external Companion BFF can serve the product without any Companion-specific host API.

## Packet 4 - Core Companion route retirement and auth collapse

### Purpose

Delete the Companion-specific host surface after the BFF is proven against generic host routes.

### In scope

1. remove the Companion router
2. remove Companion-specific auth branching and env-specific key logic
3. remove host-owned Companion orchestration service
4. remove Companion-specific route mounting from the host API app
5. keep only generic auth and generic extension-runtime routing in core

### Out of scope

1. a permanent compatibility layer
2. keeping `_is_companion_route` or `ORKET_COMPANION_API_KEY` as dormant legacy seams
3. BFF behavior changes unrelated to host route removal

### File targets

1. delete `orket/interfaces/routers/companion.py`
2. delete `orket/application/services/companion_runtime_service.py`
3. update `orket/interfaces/api.py`
4. update or remove Companion-specific tests under `tests/interfaces/` and `tests/application/`

### Guardrails

1. do not leave hidden compatibility shims unless the roadmap explicitly tracks a timed removal packet
2. do not keep `_is_companion_route` or `ORKET_COMPANION_API_KEY` as dead compatibility surfaces
3. if a temporary compatibility bridge is unavoidable, it must be contract-tracked and removal-scoped in the same lane

### Proof gate

1. host test and runtime proof pass without any Companion-specific route registration
2. the external Companion BFF still passes end-to-end proof against generic routes only
3. auth proof shows the BFF uses the generic host auth path successfully
4. `rg` over the host runtime tree finds no remaining mounted HTTP route containing `/companion/`

### Exit condition

Orket core no longer knows about Companion as a named HTTP product surface.

## Packet 5 - Authority and operator-surface closeout

### Purpose

Close the doc and operator drift created by the migration.

### In scope

1. update source-of-truth docs to the BFF-only authority model
2. remove host Companion routes from operator-facing docs
3. document the generic extension-runtime host surface
4. document the BFF-owned product surface separately from the host surface

### File targets

1. `CURRENT_AUTHORITY.md`
2. `docs/API_FRONTEND_CONTRACT.md`
3. `docs/RUNBOOK.md`
4. `docs/specs/COMPANION_UI_MVP_CONTRACT.md` or its successor
5. `docs/templates/external_extension/README.md`
6. `docs/guides/external-extension-authoring.md`

### Proof gate

1. runbook examples show only the truthful generic host runtime surface plus the BFF-owned product surface
2. the API contract no longer lists host Companion routes
3. `CURRENT_AUTHORITY.md` no longer treats host Companion routes as canonical operator seams
4. docs do not imply a repo-level Companion gateway startup command unless one exists and is canonical
5. no active spec still says the host owns Companion product orchestration

### Exit condition

The docs describe one authority story: Companion product routes live in the BFF and the host exposes only generic extension-runtime capabilities.

## Compatibility window and rollback

This migration should use the narrowest possible compatibility window.

Compatibility window rules:
1. Packets 0 and 1 require no compatibility bridge
2. Packet 2 may land the generic host transport while old host Companion routes still exist
3. Packet 3 is the only packet allowed to run with both old and new paths present
4. Packet 4 must remove the old host Companion routes rather than leave them dormant
5. no compatibility window should survive past Packet 4

Rollback rules:
1. before Packet 4, rollback means repointing the BFF to the old host Companion routes and reverting the generic transport callers if live proof fails
2. after Packet 4 starts, rollback requires an explicit revert of the route-removal changes rather than a silent compatibility shim
3. config and history migration must avoid irreversible transforms until the BFF-owned persistence story is proven
4. any Packet 0 contract delta must include rollback trigger, steps, and state recovery notes using the contract-delta template

## Packet dependency graph

Execution dependencies are strict unless an explicit packet-scoped exception is written during activation.

1. Packet 0 unlocks every other packet
2. Packet 1 must land before Packet 2 finalizes its transport contract
3. Packet 2 must land before Packet 3 can complete BFF cutover
4. Packet 3 must pass live proof before Packet 4 begins route retirement
5. Packet 5 closes only after Packet 4 succeeds

Critical path:
`Packet 0 -> Packet 1 -> Packet 2 -> Packet 3 -> Packet 4 -> Packet 5`

## Verification strategy

Verification layers are mandatory and must be reported truthfully.

1. unit:
   - generic request and response model validation
   - config and history ownership adapters on the BFF side
   - memory clear and voice-state protocol behavior
2. contract:
   - generic transport request and response schemas
   - BFF route contract behavior over the generic host surface
   - contract-delta and source-of-truth doc sync
3. integration:
   - host generic transport routes against real capability providers
   - BFF route handlers against a live host API
   - auth path verification without Companion-specific host branches
4. end-to-end:
   - BFF `chat`
   - BFF config read or write
   - BFF history retrieval
   - BFF session clear
   - BFF STT and TTS flows
   - degraded text-only mode when STT is unavailable

Live evidence rules:
1. record observed path as `primary`, `fallback`, `degraded`, or `blocked`
2. record observed result as `success`, `failure`, `partial success`, or `environment blocker`
3. if blocked, capture exact failing step and exact error
4. structural-only proof is not enough for Packets 2 through 4

## Architecture compliance checkpoints

Every active execution packet must be reviewed against `docs/architecture/ARCHITECTURE_COMPLIANCE_CHECKLIST.md`.

Minimum required checks by packet:
1. Packet 0:
   - `AC-10` authority drift control
2. Packet 1:
   - `AC-01` dependency direction
   - `AC-05` side-effect ownership
   - `AC-10` authority drift control
3. Packet 2:
   - `AC-01` dependency direction
   - `AC-05` side-effect ownership
   - `AC-07` runtime truth claims
   - `AC-10` authority drift control
4. Packet 3:
   - `AC-01` dependency direction
   - `AC-05` side-effect ownership
   - `AC-07` runtime truth claims
5. Packet 4:
   - `AC-01` dependency direction
   - `AC-05` side-effect ownership
   - `AC-10` authority drift control
6. Packet 5:
   - `AC-10` authority drift control

## Suggested execution order

1. Packet 0
2. Packet 1
3. Packet 2
4. Packet 3
5. Packet 4
6. Packet 5

Why this order:
1. Packet 0 removes contract contradiction before code moves
2. Packet 1 prevents Packet 2 from growing Companion-shaped special cases
3. Packet 2 creates the host substrate before the BFF cutover
4. Packet 3 proves the new authority split before deletion
5. Packet 4 removes host drift only after the BFF works end to end
6. Packet 5 closes operator and contract drift last

## Packet 0 ratification items

Packet 0 does not need to rediscover the plan.
It needs to ratify or explicitly override the planning defaults above.

Ratification items:
1. keep BFF-owned serialization over generic host memory for config and history, or record the approved exception
2. keep model catalog as host transport scope, or record the approved provider-contract expansion
3. keep silence-delay introspection as transport metadata, or record the approved protocol expansion
4. keep the standalone external Companion repo authority and default dev location, or record the approved successor authority
5. keep Packet 3 as the only compatibility overlap packet, or record the approved exception and removal deadline

## Draft Priority Now block

Hold only.
Do not copy this into `docs/ROADMAP.md` until requirements are accepted.

1. Companion true BFF-only migration -- Future lane candidate for moving Companion product routes and orchestration into the external BFF, exposing only generic extension-runtime transport from Orket host, and retiring all Companion-specific host HTTP and auth seams.

## Cut line

This plan should stay separate from extension package surface hardening.

It is not:
1. manifest hardening
2. install or validate UX work
3. registry or marketplace work
4. general extension route-mount discovery

It is:
1. a Companion authority-boundary migration
2. a generic extension-runtime transport extraction
3. a host-to-BFF product-surface ownership shift

## Main risks

1. the current Companion contract must be flipped before implementation or the repo will carry explicit authority conflict
2. generic substrate gaps are real; skipping them will recreate Companion-specific host logic under a different name
3. packet sequencing matters; deleting host Companion routes before external BFF proof would create false confidence
4. if config and history persistence are left vague, the migration will produce a second hidden authority seam
5. if the host transport is designed as a generic RPC instead of typed route families, the migration will widen verification risk

## Final acceptance boundary

This migration is complete only when all of the following are true:
1. the external Companion BFF completes end-to-end product flows through generic host routes only
2. Orket host exposes no Companion-named product routes
3. no Companion-specific auth branch remains in core
4. docs, contracts, and operator commands all describe the same ownership boundary
5. config and history ownership are implemented according to the Packet 0 decision with no dual authority left behind
