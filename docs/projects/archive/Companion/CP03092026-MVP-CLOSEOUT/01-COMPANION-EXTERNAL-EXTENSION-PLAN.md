# Companion External Extension Initiative Plan (Final Polish)

## Summary
- Build Companion as a true external extension repository at `C:\Source\Orket-Extensions\Companion` with independent package, CI, and release flow.
- Companion targets an experience-first Orket posture: ODR is off, and Orket host/runtime authority is limited to turn-loop/runtime seams required for safe execution, provider dispatch, config validation, security boundaries, host API semantics, runtime error behavior, and host-owned turn lifecycle behavior.
- MVP includes a real local web Companion experience surface, text chat; role/style modes; `session_memory` + `profile_memory`; speech-to-text (STT) voice input; and manual silence-delay turn-finalization control.
- Companion is the first serious external, non-game SDK validation product and must be treated as a real user-facing feature, not a throwaway shell.
- MVP UI is a real Companion experience surface while remaining thin in architecture: presentation and UX state in UI; runtime/model/memory/voice behavior behind the host API seam.
- Companion is composition-first: reuse commodity subsystems where practical; own SDK contracts, orchestration, product behavior, and integration glue.

## Product Direction, UI Architecture, and Composition Strategy
- MVP end-user surface is the local web app; CLI/TUI are non-goal except internal dev/test harnesses.
- UI must not directly call provider runtimes or internal host execution paths.
- UI must remain usable with voice disabled and usable without future avatar/expression features.
- MVP UI must be extensible without replacement for later richer presentation.
- Composition classification is mandatory per subsystem at planning time: `build`, `reuse`, `wrap`, or `defer`.
- Reused runtime subsystems must sit behind Companion-owned or SDK-owned adapter seams.
- Reused presentation libraries may be direct frontend dependencies if they do not become runtime authority.
- Expected subsystem candidates to classify include STT engine, future TTS engine, semantic retrieval backend, chat UI primitives, and avatar/expression/lip-sync presentation layers.
- Composition evaluation must include local deployability and license fit.

## Repo/Package Structure Recommendations
- Companion repo layout: `extension.yaml`, `pyproject.toml`, `src/companion_extension/`, `src/companion_app/`, `config/modes/`, `tests/`.
- Companion web app runs separately and calls host API seam; bootstrap includes recommended local proxy/origin setup.
- SDK consumption must follow external-package style, not in-repo import convenience.
- Orket side adds/updates external authoring template, validation command, and runbook for SDK-first external repos.

## SDK Gap Analysis and Public Interface Changes
- Package/release gap: harden `orket_extension_sdk` as independently installable/versioned authority.
- Capability wiring gap: provide default `model.generate` implementation via the SDK capability registry path.
- Memory gap: add `memory.write` and `memory.query` capabilities with typed models.
- Voice gap: add `speech.transcribe` and `voice.turn_control` capabilities with typed lifecycle/control models.
- Voice seam rule: STT provider is pluggable input source; host owns turn lifecycle and turn-finalization timing policy.
- Config gap: add validated config schema for role/style, memory toggles, and voice timing bounds.
- Isolation gap: enforce static import scan plus runtime guard; block internal Orket runtime imports.
- Import allowlist: stdlib, SDK modules, and third-party deps declared in Companion package/manifest authority.

## Behavioral Contracts (Modes, Memory, Voice)
- Role IDs: `researcher`, `programmer`, `strategist`, `tutor`, `supportive_listener`, `general_assistant`.
- Relationship style IDs: `platonic`, `romantic`, `intermediate`, plus optional structured `custom` style config.
- Role and relationship style are independent axes; invalid combinations are blocked at config load and turn start.
- Config precedence rule: extension defaults -> profile defaults -> session override -> turn override.
- Mode/style changes are next-turn effective unless explicitly marked UI-only preview state.
- `session_memory` in MVP is chronological append with count-based bounded recent-window retrieval per turn.
- `profile_memory` in MVP is persistent typed key/value + fact records with deterministic retrieval order and documented tie-break rules.
- `episodic_memory` is deferred and must not alter MVP `session_memory`/`profile_memory` semantics when added.
- Profile writes by Companion are restricted to explicit user-approved preferences, stable user facts (explicit confirmation-gated), and persisted Companion settings/mode state.
- Memory controls scope is profile-level default toggle plus session-level override toggle; session override resets on new session.
- Clear session memory affects current session records/artifacts only and never clears profile memory.
- Session retrieval runs before every generation turn when memory is enabled.
- Voice turn lifecycle states are `listening`, `transcribing`, `waiting_for_silence`, `finalizing`, `completed` (`completed` is terminal).
- Turn-control rule: explicit user stop/submit always overrides silence-delay waiting.
- Manual silence-delay turn-finalization control is host-enforced, voice-only, and never affects text submission behavior.
- Text submission is always explicit and unaffected by voice turn-control settings.
- If STT is unavailable, Companion degrades to text-only mode with visible UI state and no hidden failure mode.

## Phased Build Plan
- Phase 0: bootstrap external repo, package metadata, host API client scaffolding, install/validate/run scripts, and CI smoke.
- Phase 1: ship SDK/host seam hardening for memory + STT + voice turn control + config validation + error codes.
- Phase 2: ship Companion MVP product slice.
- Phase 2 UI scope includes real Companion chat experience, role/style selectors, voice controls including manual silence delay, memory controls (`clear session memory`, `inspect/edit profile settings`, memory toggle), host-API-backed thin architecture, and extensible presentation structure.
- Phase 2 runtime scope includes experience-first conversational behavior, no internal Orket runtime module dependency, composition-first capability integration through adapters, and deterministic mode resolution after config validation and before generation.
- Phase 3: run provider/runtime evaluation matrix (Ollama + LM Studio) across rig classes via public Companion seams.
- Phase 4: post-MVP enhancements include adaptive cadence, `episodic_memory`, optional audio output/TTS, and richer presentation.

## Phased Voice Interaction Plan
- MVP includes STT ingestion and manual silence-delay turn-finalization control.
- MVP transport may be chunked upload or streaming, but host API seam must expose explicit turn state transitions and stable turn-complete boundary.
- Turn-complete boundary includes both a terminal event and final result object with final transcript content.
- Partial transcripts in MVP are optional.
- Manual silence delay uses seconds and host-validated bounded min/max settings.
- Silence-delay value is profile-persisted and session-overridable.
- Adaptive cadence (later) is opt-in, bounded, transparent, and cannot silently override explicit manual settings.

## Presentation Roadmap Constraint
- MVP excludes full avatar delivery, emotion rendering, and lip-sync rendering.
- UI architecture must remain extensible toward avatar/character presentation, optional emotion/expression display, optional speech-synced mouth movement, and richer mode-tied interaction states.
- These are product-direction constraints, not MVP acceptance gates.

## Model/Runtime Evaluation Strategy (Ollama + LM Studio)
- Rig classes are `Class A` CPU/low-VRAM, `Class B` 8–12 GB VRAM, `Class C` 16–24 GB VRAM, and `Class D` 40+ GB VRAM.
- Score dimensions include reasoning quality, conversational quality, memory usefulness, latency, footprint, voice suitability (including false-finalization and interruption-fit), stability, and mode adherence.
- Output is recommendation matrix by rig class and usage profile (`chat-first`, `memory-heavy`, `voice-heavy`), not a single winner.
- Findings must identify where subsystem reuse is sufficient versus where Companion/SDK-owned behavior is required.
- Full evaluation completion requires evidence for both Ollama and LM Studio for intended matrix scope; blocked coverage is reported as partial with exact blocker details.

## Test Plan and Acceptance Criteria
- Unit tests cover mode resolution timing, memory write policy filters, silence-delay bounds, and session/profile toggle behavior.
- Contract tests cover manifest/config schema validation, capability preflight, stable error codes, and turn lifecycle payload schemas.
- Integration tests run from the external Companion repo install/run path only and verify host API seam behavior, persistence across restart, and text-only degradation.
- Integration and end-to-end runs must not rely on private in-repo convenience harnesses unavailable to the external Companion repo.
- End-to-end/live tests use public seams and record exact provider/model/runtime tuple.
- Import-boundary proof requires both static scan and runtime enforcement to pass.
- MVP acceptance requires external extension execution with no internal Orket imports.
- MVP acceptance requires text path correctness when voice is disabled or STT unavailable.
- MVP acceptance requires manual silence-delay visibility, adjustability, and effect from UI.
- MVP acceptance requires no turn finalization before configured silence window unless explicit user stop/submit.
- MVP acceptance requires intended settings round-trip through profile persistence.
- MVP acceptance requires evaluation matrix artifact classified as complete or partial with exact blockers.

## Key Risks and Sequencing
- Risk: disposable MVP UI shell; mitigation: enforce extensible thin-architecture UI design.
- Risk: bespoke subsystem sprawl; mitigation: composition-first subsystem classification and adapter use.
- Risk: third-party semantic leakage; mitigation: mandatory Companion/SDK-owned adapter seams.
- Risk: UI ambition creep; mitigation: lock MVP cut while preserving extension points.
- Risk: voice complexity creep; mitigation: manual silence-delay lands before adaptive cadence.
- Risk: memory semantics drift; mitigation: profile write policy lands before broad memory UX controls.
- Risk: backend contract churn driven by presentation work; mitigation: strict separation of presentation concerns from host/runtime authority seams.
- Sequencing rule: SDK packaging and public seam hardening complete before aggressive UI composition work.

## MVP vs Later (Explicit Scope Cut)
- MVP includes real local web Companion experience surface, thin host-API-backed architecture, role/style modes, `session_memory` + `profile_memory`, STT input, manual silence-delay turn-finalization control, and composition-first adapters where practical.
- MVP excludes audio output/TTS playback, adaptive cadence, `episodic_memory`, avatar delivery, emotion delivery, and lip-sync delivery.
- Later includes adaptive cadence, `episodic_memory`, optional audio output/TTS, richer avatar/character presentation, optional emotion/expression display, optional speech-synced lip animation, and deeper presentation polish.

## Assumptions and Defaults
- MVP is single-user and local-first.
- Host API seam is the only runtime authority seam consumed by Companion UI.
- MVP defaults are implementation defaults, not long-term architecture commitments.
- Canonical terms: host/runtime authority, host API seam, turn lifecycle, turn-finalization, turn control, `session_memory`, `profile_memory`, `episodic_memory`, manual silence-delay turn-finalization control.
