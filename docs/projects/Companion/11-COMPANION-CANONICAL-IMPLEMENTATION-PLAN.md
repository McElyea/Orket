# Companion Canonical Implementation Plan

Last updated: 2026-03-09
Status: In Progress
Owner: Orket Core
Source authority: `docs/projects/Companion/01-COMPANION-EXTERNAL-EXTENSION-PLAN.md`
Supporting inputs: `docs/projects/Companion/00-GAP-SUMMARY-AND-DEPENDENCY-MAP.md`, `docs/projects/Companion/02-SDK-PACKAGE-HARDENING.md` through `docs/projects/Companion/10-IMPORT-ISOLATION-HARDENING.md`

## 1. Objective

Deliver Companion as a real external extension product with a thin client architecture over host-owned runtime authority.

Non-negotiable authority constraints:
1. Host API seam owns prompt assembly, memory retrieval, generation orchestration, session state, and voice turn-finalization behavior.
2. Companion external repo owns presentation, UX state, and typed consumption of public host seams.
3. No product-significant runtime authority is duplicated in Companion UI code or Companion-repo backend shims.

## 1.1 Current Execution Snapshot (2026-03-08)

Phase 0 progress:
1. Slice A implemented:
   - SDK-local packaging authority (`orket_extension_sdk/pyproject.toml`)
   - `py.typed` marker and changelog scaffold
   - SDK import-isolation contract tests
   - clean editable install proof for base and extras
2. Slice B implemented:
   - SDK standalone validators (`python -m orket_extension_sdk.validate`, `python -m orket_extension_sdk.import_scan`)
   - Host CLI external validation path (`orket ext validate`)
   - external-extension authoring guide and template surface in `docs/templates/external_extension/`
   - local external Companion bootstrap repo created at `C:\Source\Orket-Extensions\Companion` with install/validate/test proof
3. Slice A release hardening implemented:
   - SDK package release workflow (`.gitea/workflows/sdk-package-release.yml`)
   - SDK tag/version guard script (`scripts/sdk/check_sdk_tag_version.py`)
   - SDK local build/test/publish commands (`orket_extension_sdk/Makefile`)
4. Phase 0 bootstrap convenience implemented:
   - host CLI scaffold command (`orket ext init <path>`)
5. Slice C groundwork in progress:
   - SDK memory and voice capability contracts (`orket_extension_sdk/memory.py`, `orket_extension_sdk/voice.py`)
   - capability vocabulary extended for `memory.write`, `memory.query`, `speech.transcribe`, `voice.turn_control`
   - runtime capability registration now includes host-backed `model.generate`, SQLite-backed `memory.write`/`memory.query`, and null-provider defaults for speech/voice seams
6. Slice E implemented:
   - runtime import guard lifecycle (`orket/extensions/import_guard.py`) installed for SDK workload module load + execution scope
   - blocked dynamic imports of internal `orket.*` namespaces now fail with `E_EXT_IMPORT_BLOCKED` while allowing `orket_extension_sdk.*`
   - integration coverage for guard block/allow/no-leak behavior (`tests/runtime/test_extension_import_guard.py`)
7. Slice D foundation implemented:
   - host companion config models (`orket/application/services/companion_config_models.py`) with enum authority, structural validation, and silence-delay bounds clamping
   - deterministic 4-layer resolver (`orket/application/services/config_precedence_resolver.py`) with pending-next-turn consumption semantics
   - mode scope policy helper (`orket/application/services/mode_change_policy.py`) for `session` vs `pending_next_turn` updates
   - external extension template config schema/defaults aligned to structured mode+voice shape and validated by runtime test coverage
8. Slice F groundwork implemented:
   - scoped memory store (`orket/services/scoped_memory_store.py`) with explicit session/profile operations and clear-session support
   - profile write policy enforcement (`orket/services/profile_write_policy.py`) with allowlist prefixes and `user_fact.*` confirmation gate
   - SDK memory provider now routes through scoped store and enforces memory toggles plus profile policy (`orket/capabilities/sdk_memory_provider.py`)
9. Slice G groundwork implemented:
   - host voice turn controller and host STT seam providers (`orket/capabilities/sdk_voice_provider.py`)
   - capability registry defaults now wire host voice-turn control with bounded silence-delay configuration and host STT unavailable fallback
10. Slice H groundwork implemented:
    - host runtime service (`orket/application/services/companion_runtime_service.py`) now owns Companion config/session/history/chat/memory-clear/voice-state/voice-control/transcribe behavior
    - dedicated Companion router surface (`orket/interfaces/routers/companion.py`) exposed under both `/v1/companion/*` and `/api/v1/companion/*` with existing API-key auth dependency
    - integration tests cover service behavior and router contracts (`tests/application/test_companion_runtime_service.py`, `tests/interfaces/test_companion_router.py`, `tests/interfaces/test_companion_api_alias_routes.py`)
11. Slice I template MVP groundwork implemented:
    - external template API client expanded to full Companion host seam (`status`, `config`, `history`, `chat`, `voice`, `clear-session`)
    - external template web app now includes FastAPI gateway routes plus static MVP chat/control UI assets in `src/companion_app/static/`
    - `ext init` and template server/config tests now verify richer scaffold paths and static UI serving behavior

## 2. Scope and Phase Model

Initiative phases:
1. Phase 0: foundation bootstraps
2. Phase 1: host/runtime seam hardening for Companion features
3. Phase 2: Companion MVP product slice
4. Phase 3: provider/runtime evaluation matrix
5. Phase 4: post-MVP enhancements

MVP includes:
1. External Companion repo and install/validate/run flow
2. Real local web chat UI
3. Role/style mode controls
4. `session_memory` and `profile_memory`
5. STT voice input
6. Manual silence-delay turn-finalization control
7. Text-only degradation when STT is unavailable

MVP excludes:
1. Audio output/TTS playback
2. Adaptive cadence
3. `episodic_memory`
4. Avatar, expression, and lip-sync delivery

## 3. Dependency and Execution Order

Execution order is strict unless explicitly marked parallel.

1. Slice A (parallel): SDK package hardening
2. Slice B (parallel): external repo bootstrap
3. Slice C: capability wiring
4. Slice D (parallel after Slice C): config and mode schema
5. Slice E (parallel after Slice C): import isolation hardening
6. Slice F (after Slice C): memory subsystem split
7. Slice G (after Slice C): voice/STT turn control
8. Slice H (after Slices C, D, E, F, G): host API seam
9. Slice I (after Slices B and H): Companion MVP product
10. Slice J (after Slice I): provider/runtime matrix
11. Slice K (after Slice J): post-MVP enhancements

Critical path:
`A -> C -> F -> H -> I`

## 4. Workstream Plan

### Slice A - SDK Package Hardening (Phase 0)

Goals:
1. Make `orket_extension_sdk` independently installable and versioned.
2. Enforce SDK isolation from `orket.*` internals.
3. Establish SDK release workflow and SemVer contract.

Deliverables:
1. `orket_extension_sdk/pyproject.toml`
2. Single-source version authority (`__version__.py`)
3. SDK extras (`tts`, `testing`) and `py.typed`
4. SDK changelog scaffold
5. CI packaging/install proof for clean environments

Exit criteria:
1. Clean-venv install works for base SDK and extras.
2. SDK imports succeed without requiring `orket` package imports.
3. AST import checks show no `orket.*` internal imports.

### Slice B - External Repo Bootstrap (Phase 0)

Goals:
1. Create Companion as independent repo authority at `C:\Source\Orket-Extensions\Companion`.
2. Provide repeatable install/validate/run scripts for Windows and Unix.
3. Add external-extension template and runbook support in Orket repo.

Deliverables:
1. Companion repo skeleton (`extension.yaml`, `pyproject.toml`, `src/`, `config/`, `tests/`, scripts)
2. `orket ext validate <path>` CLI support
3. SDK standalone validation and import scan modules
4. External extension authoring guide and CI template

Exit criteria:
1. Companion repo validates and runs from its own workspace.
2. Validation tools work without importing `orket`.
3. CI smoke path covers manifest validation, import scan, and tests.

### Slice C - Capability Wiring (Phase 1)

Goals:
1. Wire missing capabilities required by Companion:
   - `model.generate`
   - `memory.write`
   - `memory.query`
   - `speech.transcribe`
   - `voice.turn_control`
2. Provide typed Pydantic models and provider protocols.
3. Align capability failure codes with existing host error conventions.

Deliverables:
1. SDK models in concern-specific modules (`llm.py`, `memory.py`, `voice.py`)
2. Host provider wiring for model, memory, STT, and voice control seams
3. Capability registry updates and validation coverage

Exit criteria:
1. New capabilities are discoverable and invocable through registry paths.
2. `model.generate` produces real completions via host provider path.
3. Capability models validate independently of internal host imports.

### Slice D - Config and Mode Schema (Phase 1)

Goals:
1. Define Companion mode/memory/voice config schema.
2. Implement deterministic 4-layer precedence:
   - extension defaults
   - profile defaults
   - session overrides
   - pending next-turn overrides
3. Enforce next-turn timing semantics for mode changes.

Deliverables:
1. Companion config schema and enum authority
2. Host config precedence resolver
3. Mode change policy service
4. Structural validation for custom style and bounds enforcement for silence delay

Exit criteria:
1. Config precedence behavior is deterministic and tested.
2. Mode/style changes are next-turn effective through full host/API path.
3. Session overrides reset on new session.

### Slice E - Import Isolation Hardening (Phase 1)

Goals:
1. Preserve static import scanning.
2. Add runtime import guard during extension workload execution.
3. Prevent dynamic import bypass of internal `orket.*` paths.

Deliverables:
1. `ExtensionImportGuard` + scoped lifecycle management
2. Workload execution wiring under import guard context
3. Standalone import-scan utility for external CI

Exit criteria:
1. Dynamic imports of internal modules are blocked during extension execution.
2. Guard does not leak outside extension run context.
3. Static and runtime import enforcement both pass.

### Slice F - Memory Subsystem Split (Phase 1)

Goals:
1. Split memory into `session_memory` and `profile_memory`.
2. Add profile write policy enforcement.
3. Support memory toggles and clear-session operation.

Deliverables:
1. `ScopedMemoryStore` with explicit scope-aware operations
2. Schema migration for scope/session/key indexing
3. Profile write policy allowlist and user-confirmed facts gate
4. Retrieval-order rules for deterministic behavior

Exit criteria:
1. Session memory is isolated by `session_id`.
2. Profile memory supports exact-key and deterministic list/query flows.
3. `clear_session` never touches profile memory.
4. Pre-turn memory retrieval behavior is wired and bounded.

### Slice G - Voice/STT Turn Control (Phase 1)

Goals:
1. Implement host-owned voice turn lifecycle FSM.
2. Add STT provider seam and one working local provider implementation.
3. Enforce manual silence-delay control and explicit submit/stop override.

Deliverables:
1. Voice state/command models and valid-transition contract
2. Host voice controller and STT provider implementations (including null provider)
3. Voice API routes and config endpoints
4. Text-only degradation handling when STT unavailable

Exit criteria:
1. Explicit stop/submit overrides silence wait immediately.
2. Silence delay is host-validated, bounded, and persisted profile-side with session override.
3. Voice unavailability is visible and non-breaking for text chat.

### Slice H - Host API Seam (Phase 1 -> 2 bridge)

Goals:
1. Expose Companion-scoped MVP host routes.
2. Keep host API as single runtime authority seam consumed by Companion.
3. Standardize structured error envelopes and CORS behavior.

Deliverables:
1. `/api/v1/companion` router and request/response models
2. MVP-minimum endpoint set:
   - chat/session/history core
   - config read/update
   - voice state/submit/transcribe/config
   - session memory clear
   - status
3. CORS configuration for local web app origins
4. Typed Companion API client ownership decision executed (Companion-owned for MVP)

Exit criteria:
1. UI can complete core chat loop through host API only.
2. Structured error codes are stable and contract-tested.
3. No duplicate orchestration path appears in Companion repo.

### Slice I - Companion MVP Product (Phase 2)

Goals:
1. Ship a real local web Companion experience using the host API seam.
2. Keep workload entrypoint thin for manifest/install compatibility.
3. Deliver extensible UI without importing excluded MVP features.

Deliverables:
1. Thin workload entrypoint (`workload.py`)
2. Companion-owned host API client
3. Web app with:
   - chat panel
   - role/style controls
   - voice controls and state
   - memory controls
   - status bar
4. Companion config templates (`config/modes`, `config/styles`, `config/defaults.json`)

Exit criteria:
1. Text path works when STT unavailable.
2. Manual silence-delay control is visible and behaviorally effective.
3. Mode and memory settings round-trip through persisted profile state.
4. Companion UX is functional without host-authority duplication.

### Slice J - Provider/Runtime Evaluation Matrix (Phase 3)

Goals:
1. Evaluate Companion behavior across Ollama and LM Studio.
2. Produce rig-class recommendations (`A`, `B`, `C`, `D`) by usage profile.
3. Record partial/blocked coverage with exact blockers.

Deliverables:
1. Matrix artifact with scored dimensions:
   - reasoning
   - conversational quality
   - memory usefulness
   - latency
   - footprint
   - voice suitability
   - stability
   - mode adherence
2. Explicit completeness status (`complete` or `partial` with blockers)

Exit criteria:
1. Both runtime families are evaluated or exact blocker evidence is recorded.
2. Recommendations are profile- and rig-specific, not single-winner.

### Slice K - Post-MVP Enhancements (Phase 4)

Deferred scope:
1. Adaptive cadence
2. `episodic_memory`
3. Optional audio output/TTS
4. Avatar/expression/lip-sync presentation enhancements

Guardrail:
1. Deferred features must not alter MVP contracts for session/profile memory, mode precedence, and host-owned turn lifecycle semantics.

## 5. Verification Strategy by Layer

Verification layers are mandatory and must be reported truthfully.

1. Unit:
   - config merge semantics
   - write-policy filters
   - silence-delay bounds
   - FSM transition rules
2. Contract:
   - manifest/config schema validation
   - capability model validation
   - host API payload/error schema stability
3. Integration:
   - external Companion install/validate/run path
   - host API chat/memory/voice flows with real host runtime
   - import isolation static + runtime enforcement
4. End-to-end:
   - Companion UI to host API conversational flow
   - text-only degradation path
   - voice flow with explicit submit/stop behavior

Live integration evidence rules:
1. Record observed path (`primary`, `fallback`, `degraded`, `blocked`).
2. Record observed result (`success`, `failure`, `partial success`, `environment blocker`).
3. If blocked, capture exact failing step and exact error.

## 6. Acceptance Gate by Phase

Phase 0 completion gate:
1. SDK is independently installable and versioned.
2. External Companion repo validates/runs with CI smoke.

Phase 1 completion gate:
1. Capability, memory, config, voice, import hardening, and host API seam are implemented and contract/integration tested.
2. Host API remains the only runtime authority seam for Companion UX.

Phase 2 completion gate:
1. MVP feature set works from external Companion repo against live host runtime.
2. Voice-disabled and STT-unavailable text path remains correct.

Phase 3 completion gate:
1. Matrix artifact is complete or explicitly partial with blockers.

Phase 4 completion gate:
1. Deferred features ship without violating locked MVP contracts.

## 7. Traceability Matrix

| Source doc | Covered by slice |
| --- | --- |
| `00-GAP-SUMMARY-AND-DEPENDENCY-MAP.md` | Slices A-K sequencing and severity-driven priority |
| `01-COMPANION-EXTERNAL-EXTENSION-PLAN.md` | Whole plan authority and phase model |
| `02-SDK-PACKAGE-HARDENING.md` | Slice A |
| `03-CAPABILITY-WIRING.md` | Slice C |
| `04-MEMORY-SUBSYSTEM-SPLIT.md` | Slice F |
| `05-VOICE-STT-TURN-CONTROL.md` | Slice G |
| `06-CONFIG-AND-MODE-SCHEMA.md` | Slice D |
| `07-HOST-API-SEAM.md` | Slice H |
| `08-EXTERNAL-REPO-BOOTSTRAP.md` | Slice B |
| `09-COMPANION-MVP-PRODUCT.md` | Slice I |
| `10-IMPORT-ISOLATION-HARDENING.md` | Slice E |

## 8. Execution Notes

1. This file is the canonical execution pointer for the Companion lane in `docs/ROADMAP.md`.
2. Supporting `00-10` docs remain authoritative inputs but not the active roadmap pointer.
3. Closeout must archive completed phase-scoped docs without archiving the initiative-level plan while future phases remain.
