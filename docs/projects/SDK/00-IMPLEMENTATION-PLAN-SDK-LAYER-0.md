# SDK Layer 0 Implementation Plan

Date: 2026-02-28  
Status: active (gameplay tuning can pause while SDK direction is refined)  
Scope: Build TextMystery and SDK together in vertical slices, with minimal Orket runtime changes.

## Intent

Create the smallest standalone SDK that removes obvious boilerplate pressure from TextMystery, while keeping TextMystery first-class and improving gameplay quality in the same loop.

This plan is Layer 0:
1. Minimal extensible seam.
2. Audio-focused capability path.
3. Deterministic artifact-first run model.
4. No broad platform abstractions.

Layer-0 center reframe:
1. `L0.3 Gameplay Kernel v1` is the center of Layer 0.
2. SDK infrastructure is successful only if Gameplay Kernel outcomes improve playability and transcript quality.

## Grounded Findings From TextMystery (Current State)

Observed in `C:\Source\Orket-Extensions\TextMystery`:

1. Audio is not implemented yet.
2. There is a tiny TTS hook only:
   - `src/textmystery/engine/tts.py` defines `VoiceProvider` and `NoopVoiceProvider`.
   - CLI uses the noop provider directly in `src/textmystery/cli/main.py`.
3. Determinism and replay discipline already exist and are strong:
   - seed-based world generation, parity tests, leak checks, run artifact support.
4. Live integration exists as parity/leak endpoints:
   - `src/textmystery/interfaces/live_contract.py`
   - `src/textmystery/cli/live_server.py`
5. Obvious extraction pressure:
   - provider wiring and IO hooks in CLI path
   - artifact metadata conventions for replay
   - manifest/capability declaration seam missing

## Pain Points To Fix Without Over-Engineering

1. Capability injection is implicit and ad-hoc.
2. Voice/Audio provider lifecycle has no standard capability contract.
3. Artifact conventions are present but not standardized as SDK primitives.
4. Integration surface between game and Orket is contract-like but not an SDK package.
5. Future audio IO will otherwise land as per-game boilerplate.
6. Companion hint policy can still feel repetitive without stronger target cooldown and NPC-aware suggestion routing.
7. Disambiguation UX still needs clearer command handling and phrasing for partial natural-language prompts.
8. Cross-suspect coaching quality is now the main gameplay feel lever (engine correctness is largely stable).

## Gameplay Correction Pack (Verified + Locked)

This pack is now part of Layer 0 so game quality improvements do not drift.

### Already true in current code (do not re-solve)

1. `WHO_HAD_ACCESS` is already answered from `world.access_graph`, not from a raw fact string.
2. `DID_YOU_HAVE_ACCESS` is already special-cased and rendered as a boolean answer path.

### Must change next (high impact)

1. Move toward typed fact payloads for conversational facts.
   - Current: `Fact.value: str`
   - Target: `Fact.value: dict[str, Any] | str` in transition, then typed-only later.
2. Replace `FACT_LINKAGE_ANCHOR_1` blob with at least:
   - one presence claim
   - one witness claim
3. Add playability invariants in worldgen:
   - triangulation invariant (two-step inference path)
   - typed answerability invariant by intent/surface
   - escalation invariant (time/access/witness leads each unlock follow-up)
4. Replace universal `FACT_NOISE_1` with per-NPC secret facts and controlled overlap by surface.
5. Expand classifier/entity extraction to set stable `place_ref` and `object_id` for core nouns (service door, boardroom, audit drive).

## Locked Decisions (D1-D11)

### D1: Fact payload shapes v1 (minimal contract)

Allowed typed payload shapes in v1:
1. `time_anchor`: `{"kind":"time_anchor","time":"11:03 PM"}`
2. `presence`: `{"kind":"presence","who":"NICK_VALE","where":"SERVICE_DOOR","when":"11:03 PM"}`
3. `witness`: `{"kind":"witness","witness":"NADIA_BLOOM","who":"NICK_VALE","where":"SERVICE_DOOR","when":"11:03 PM"}`
4. `access_method`: `{"kind":"access_method","where":"SERVICE_DOOR","method":"KEYCARD"}`
5. `object`: `{"kind":"object","object":"AUDIT_DRIVE"}`
6. `action`: `{"kind":"action","who":"NICK_VALE","action":"MOVED","object":"AUDIT_DRIVE","when":"11:03 PM","where":"ARCHIVE"}`
7. `secret`: `{"kind":"secret","npc":"GABE_ROURKE","domain":"FINANCE","hint":"offbook expense sheet"}`

Transition note:
1. `Fact.value` remains `dict[str, Any] | str` during migration.
2. New gameplay facts must use typed payloads.

### D6: Fact payload includes explicit kind

All typed fact payloads must include:
1. `{"kind": "<time_anchor|presence|witness|access_method|object|action|secret>", ...}`

Why:
1. Removes key-inference ambiguity in renderer and validators.
2. Keeps deterministic parsing simple and explicit.

### D2: Render answer-shape validation gate

`render.py` must enforce intent-to-shape compatibility and never emit category-mismatched answers.

Required mapping:
1. `WHERE_WAS` -> requires `where`.
2. `WHEN_WAS` -> requires `when` or `time`.
3. `DID_YOU_SEE` -> requires `who` or `witness` (or boolean-style answer path).
4. `WHO_HAD_ACCESS` -> must come from `access_graph`, never from `Fact.value`.
5. `DID_YOU_HAVE_ACCESS` -> boolean answer path, optional method text allowed.
6. `WHAT_DO_YOU_KNOW_ABOUT` -> scoped summary and nudge topics only.
7. `UNCLASSIFIED_AMBIGUOUS` -> clarify response, never random factual output.

Fallback policy:
1. If answer shape is invalid, renderer must return clarify/redirect text.

### D8: Intent -> required fields validator mapping

Validator must enforce these requirements:
1. `WHERE_WAS`:
   - query has `place_ref`, or selected payload has `where`.
2. `WHEN_WAS`:
   - query has `time_ref`, or selected payload has `when`/`time`.
3. `DID_YOU_SEE`:
   - query has or infers stable target context; selected payload includes `who` and optional `where`/`when`.
4. `WHO_HAD_ACCESS`:
   - query has `place_ref`; answer must come from `access_graph[place_ref]`.
5. `DID_YOU_HAVE_ACCESS`:
   - query has `place_ref`; answer is boolean (or refusal), optional method text.

Note:
1. This mapping prevents place/object confusion from re-entering rendering behavior.
2. `DID_YOU_HAVE_ACCESS` refers to place access only in v1 (doors/rooms/routes), not object possession.
3. Object possession questions route to `DID_YOU_DO` or `WHAT_DO_YOU_KNOW_ABOUT` with `object_id`.

### D3: Discovery/unlock model requirement

Gameplay Kernel must include explicit discovery and lead unlock behavior.

Minimum model:
1. Runtime discovery state:
   - `discoveries: set[str]`
2. Frozen world lead map:
   - `lead_unlocks: dict[str, list[str]]`

Minimum behavior:
1. New evidence unlocks follow-up targets (place/object/subject ids).
2. Companion nudges prioritize undiscovered unlocks before generic hints.

### D9: Discovery keys are stable and namespaced

Discovery key format is locked:
1. `disc:fact:<FACT_ID>`
2. `disc:place:<PLACE_ID>`
3. `disc:object:<OBJECT_ID>`
4. `disc:npc:<NPC_ID>`

These keys are replay-visible artifacts and must remain stable.

### D4: No universal noise rule

1. Universal `FACT_NOISE_1` is forbidden in v1 gameplay generation.
2. Each NPC has one secret fact.
3. Controlled overlap is required by surface domain, but facts remain distinct.

### D5: Workload context capability boundary

1. Workloads must resolve dependencies via `ctx.capabilities`.
2. Workloads must not instantiate IO providers directly.
3. `WorkloadContext` carries capabilities + trace + artifact writer as mandatory infrastructure.

### D7: Canonical place/object IDs

Canonical place IDs:
1. `SERVICE_DOOR`
2. `BOARDROOM`
3. `ARCHIVE`

Canonical object IDs:
1. `AUDIT_DRIVE`
2. `BOARDROOM_FEED`

When known, `place_ref` and `object_id` must use these exact strings.

### D10: Two-step triangulation definition

Triangulation is defined as:
1. Culprit identity cannot be derived from any single answerable fact.
2. Culprit resolution requires at least two distinct discovered items.
3. One item must be a witness claim.
4. The second item must be either:
   - a presence claim, or
   - an access-list route that places culprit plausibly.

### D11: Resolver matching strategy (dynamic-first, deterministic)

Resolver behavior is locked to avoid brittle hardcoded fact-id routing:
1. Resolver must perform deterministic dynamic fact search before static fallback mapping.
2. Dynamic search iterates `sorted(npc_knowledge)` for deterministic parity.
3. Dynamic candidate selection filters by:
   - intent compatibility
   - surface compatibility
   - payload constraints from canonical query (`place_ref`, `object_id`, `subject_id`, `time_ref`)
4. Guard check applies to matched candidate fact.
5. Static `_fact_for_intent` mapping remains as compatibility fallback only if no dynamic candidate is found.

Non-goal:
1. No inference engine, no graph traversal solver, no LLM reasoning in resolver.

### D12: Companion hint policy (deterministic, non-repeating)

1. Hint generation must suppress repeated target suggestions with stable hint markers:
   - `disc:hint:<disc-key>`
2. Hint selection must avoid:
   - exact recent nudge repeats
   - semantic repeats of recently asked player questions
3. Hint policy should prefer corroboration chain suggestions after witness/presence/action answers.
4. Hint policy should be NPC-aware for access prompts:
   - if current NPC cannot answer access, suggest an NPC switch deterministically.

### D13: Disambiguation command behavior

1. Disambiguation prompt must accept control commands:
   - `back`, `help`, `quit`
2. Disambiguation prompt must accept:
   - numeric angle choice
   - named angle choice
   - full sentence with inferred angle
3. Disambiguation should not trap the player in invalid-angle loops.

## Architecture Decision: SDK Location

Decision:
1. Keep SDK as a standalone project/package, versioned independently from Orket and TextMystery.
2. Keep Orket integration as a thin runtime bridge only.

Rationale:
1. Cleaner semantic versioning for extension authors.
2. Keeps SDK pure and reusable across extension repos.
3. Prevents Orket-internal concerns from leaking into public SDK contracts.
4. Minimal downside: one extra dependency boundary and release pipeline.

Practical structure:
1. New standalone repo/package rooted at `c:\Source\OrketSDK` (recommended package name: `orket-extension-sdk`).
2. TextMystery depends on SDK package.
3. Orket depends on SDK package only for runtime bridge and type-level integration.

SDK workspace lock:
1. All SDK layer-0 implementation work assumes local root path `c:\Source\OrketSDK`.
2. Orket and TextMystery consume SDK via dependency/reference, not by embedding SDK source under either repo.

SDK repo plumbing lock:
1. Package name: `orket-extension-sdk`.
2. Version policy: `0.y.z` during layer-0 and layer-1 stabilization.
3. Local consumption mode during development: editable install (`pip install -e c:\Source\OrketSDK`) in both Orket and TextMystery environments.
4. Publish mode remains deferred until layer-0 exit criteria are met.

## Layer 0 Contract (Locked)

1. Public seam:
   - `Workload.run(ctx, input) -> WorkloadResult`
2. Manifest seam:
   - `extension.yaml` primary, JSON accepted.
3. Capability seam:
   - explicit `CapabilityProvider` and `CapabilityRegistry`.
4. Observability seam:
   - `ctx.trace.emit(event_type, payload)`.
5. Engine-internal seam remains private:
   - `TurnResult` is not public.

## Layer 0 Slices (Build SDK + Game Together)

## Slice L0.1: Boot SDK Skeleton + Manifest

Goal:
1. Standalone SDK package with `manifest`, `result`, `workload` contracts.

Implementation:
1. Create `Manifest`, `WorkloadContext`, `WorkloadResult`, `Issue`, `ArtifactRef`.
2. Implement `load_manifest()` and `validate_manifest()`.
3. Add YAML + JSON parsing support.

Game integration:
1. Add `extension.yaml` to TextMystery extension path using SDK schema.
2. Declare required capabilities initially: `console`, `audio_output` (audio_input optional until implemented).

Acceptance:
1. Manifest parses and validates deterministically.
2. TextMystery can be described by SDK manifest without custom side contracts.

## Slice L0.2: Capability Core + Noop Providers

Goal:
1. Make capability injection explicit and testable.

Implementation:
1. Add `CapabilityProvider` and `CapabilityRegistry`.
2. Add interfaces: `Console`, `AudioOutput`, `AudioInput`, `Clock`, `KVStore`.
3. Provide in-memory noop providers in SDK testing package.

Game integration:
1. Replace direct `NoopVoiceProvider` CLI wiring with capability retrieval from context/provider registry.
2. Keep behavior unchanged (still noop output path).

Acceptance:
1. Game runtime path no longer instantiates provider implementation directly.
2. Provider swap is possible without touching game logic.

## Slice L0.3: Gameplay Kernel v1 (Center Slice)

Goal:
1. Make interrogation output conversationally correct and progressively discoverable.

Implementation:
1. Update `Fact` model to support typed payload values (transition-safe).
2. Implement locked payload shapes from D1.
3. Replace linkage blob anchor with witness + presence facts.
4. Update world generator to emit structured access/time/witness/object/action facts.
5. Remove universal noise fact and generate per-NPC guarded secrets with overlap by surface.
6. Add worldgen invariants for triangulation, typed answerability, and escalation.
7. Implement answer-shape validation gate in renderer per D2.
8. Implement minimal discovery/unlock model per D3.
9. Update classifier mapping to better populate `place_ref` and `object_id`.
10. Add canonical ID validation for places/objects per D7.
11. Upgrade resolver from static-id-first to dynamic matching per D11.

Game integration:
1. Keep core gameplay in TextMystery runtime; only extract reusable formatting/helpers if they are truly generic.
2. Preserve deterministic behavior and replay artifacts while changing semantics.

Acceptance:
1. Interrogation transcripts no longer emit category-mismatched answers.
2. At least one case path requires two-step triangulation.
3. Refusal overlap is meaningful, not monotone.
4. Existing determinism/leak constraints remain green.
5. Per-intent shape tests exist and pass for all active `IntentId` routes.
6. Transcript fixture includes at least:
   - one witness claim
   - one presence claim
   - one access list answer
   - one object/action tie-in
7. A dedicated test fails if culprit can be derived from a single isolated fact.
8. Discovery artifacts use stable namespaced keys per D9.
9. Resolver returns relevant known facts via dynamic matching even when static fact-id mapping would miss.
10. Resolver remains deterministic across reruns (sorted candidate selection).

## Slice L0.4: Artifact Writer + Trace Hook

Goal:
1. Standardize run outputs for replay and diagnostics.

Implementation:
1. SDK artifact writer with namespaced write + digest generation.
2. Add `ctx.trace.emit(...)` helper and stable event shape.

Game integration:
1. Write transcript and summary through SDK artifact writer.
2. Emit trace events for key phases (ask/decision/response/accuse/reveal).

Acceptance:
1. Artifacts include digest metadata.
2. Replay-critical events are captured without exposing Orket internal turn schema.

## Slice L0.5: Audio Output Real Provider (Minimal)

Goal:
1. Introduce real audio playback with minimal API and deterministic artifact references.

Implementation:
1. Implement one reference `AudioOutput` provider in SDK-adjacent adapter package.
2. Keep API simple: play from file/path or bytes with optional spec.
3. Persist output artifact references and metadata.

Game integration:
1. Companion or NPC response playback route via `AudioOutput` capability.
2. If provider unavailable, fallback to noop provider without game failure.

Acceptance:
1. Audio playback works locally when provider is configured.
2. Run remains playable with noop fallback.

## Slice L0.6: Audio Input Capture (Artifact-First)

Goal:
1. Add mic capture without polluting game logic.

Implementation:
1. Implement minimal `AudioInput` provider lifecycle:
   - open/start/stop
2. Persist:
   - `artifacts/audio/input.wav`
   - `artifacts/audio/input.meta.json` including digest and capture metadata

Game integration:
1. Optional voice question input path (off by default).
2. Deterministic replay mode reads captured artifact instead of live mic.

Acceptance:
1. Game can run with or without mic.
2. Replay parity uses stored artifact references.

## Slice L0.7: Orket Runtime Bridge (Minimal Change)

Goal:
1. Run SDK workloads inside Orket with minimal runtime churn.

Implementation:
1. Add SDK workload execution path in Orket extension manager/runtime bridge.
2. Preserve legacy `RunPlan` path during migration.
3. Map SDK result to internal runtime result types privately.

Acceptance:
1. TextMystery SDK workload runs under Orket.
2. Existing legacy extensions still run.

## Concrete Extraction Map (TextMystery -> SDK)

1. `src/textmystery/engine/tts.py`
   - Extract interface semantics into SDK capability contracts (`AudioOutput` and optional voice profile metadata).
2. `src/textmystery/cli/main.py`
   - Replace direct provider creation with capability-based retrieval from context.
3. `src/textmystery/engine/worldgen.py`
   - Keep domain logic local; apply typed fact payloads, witness/presence anchors, and playability invariants.
4. `src/textmystery/engine/render.py`
   - Move from string parsing fallbacks to typed fact rendering by intent.
5. `src/textmystery/engine/classify.py`
   - Improve stable extraction for `place_ref` and `object_id`.
6. `src/textmystery/engine/persist.py`
   - Reuse digest and artifact discipline via SDK artifact helper API.
7. `src/textmystery/interfaces/live_contract.py`
   - Keep game-domain logic local; extract only generic run/trace/artifact contract helpers to SDK.
8. `src/textmystery/engine/runtime.py`
   - Keep gameplay logic local; inject only infrastructure via `WorkloadContext`.

## Test Plan (Layer 0)

1. SDK contract tests:
   - manifest parse/validate
   - capability registry behavior
   - workload result model validation
2. SDK determinism tests:
   - determinism harness stable output + artifact digest comparisons
3. Game tests:
   - existing parity and leak suites remain green
   - new capability-injected runtime path tests
   - gameplay semantics tests for typed answerability, witness/presence triangulation, and escalation unlocks
   - answer-shape validation tests by `IntentId`
   - discovery/unlock progression tests
   - resolver dynamic-match tests (intent/surface/query constraint filtering)
   - resolver determinism tests (stable candidate choice under fixed seed/input)
4. Integration tests:
   - TextMystery as SDK workload via Orket bridge
   - legacy extension path still works

## Execution Sequence (PR-sized)

1. PR1:
   - typed payload support in `Fact.value`
   - render answer-shape validation gate and clarify fallback
2. PR2:
   - worldgen witness + presence anchors
   - stable place/object labels for `SERVICE_DOOR` and `AUDIT_DRIVE`
   - add minimal discovery recording (silent; no companion behavior change yet)
3. PR3:
   - per-NPC secrets and overlap invariant
   - reveal updates for secret/guard clarity
4. PR4:
   - resolver dynamic-match upgrade (sorted deterministic candidate selection)
   - discovery/unlock model consumption
   - companion nudge prioritization from undiscovered unlocks
5. PR5:
   - SDK manifest/capability core/noop providers integration hardening
6. PR6:
   - companion hint policy hardening (cooldown, target markers, NPC-aware routing)
   - disambiguation UX hardening (Angle prompt command handling + shorthand intent mapping)

## Checkpoint Snapshot (Stop/Resume Safety)

This section is a recovery checkpoint so work can pause without losing implementation context.

### Implemented now (as of 2026-02-28)

1. Typed facts with `kind` are in place for core anchors (`time`, `presence`, `witness`, `access_method`, `object`, `action`, `secret`).
2. `WHO_HAD_ACCESS` uses `access_graph` and requires `place_ref`.
3. `DID_YOU_HAVE_ACCESS` is place-access only in resolver semantics.
4. Namespaced discovery keys are being recorded in runtime.
5. Discovery lead map (`lead_unlocks`) exists in world model/generation.
6. UI disambiguation seam exists in runtime via `needs_disambiguation`.
7. Runtime + CLI disambiguation path is implemented (`needs_disambiguation` consumed in CLI with angle forcing).
8. First-person render behavior for speaker-owned presence/witness/action is implemented with regression coverage.
9. Cooperative-anchor rule is active in worldgen.
10. Resolver dynamic-first deterministic matching is implemented and tested.
11. Companion policy upgrades are in place:
   - semantic repeat suppression
   - nudge pacing gate (`nudge_min_gap`)
   - witness-chain-first suggestions
   - target hint markers (`disc:hint:*`)
   - NPC-aware access routing for hints
12. Local deterministic test suite remains green after gameplay-kernel and companion policy changes.

### Remaining focus (next high-impact work)

1. Companion quality pass:
   - better cross-suspect handoff wording and ranking.
   - explicit “already attempted” suppression keyed by NPC + intent + target.
2. Clarify UX quality:
   - enrich access clarifications with concrete place choices (`SERVICE_DOOR`, `BOARDROOM`, `ARCHIVE`).
3. Tone/variation pass:
   - tighten DONT_KNOW/REFUSE phrase pools by intent while preserving determinism.
4. SDK extraction pacing:
   - pause new gameplay changes when extraction-ready seams are identified and stable.

### Resume checklist (if paused)

1. Run tests:
   - `python -m pytest tests -q` in `C:\Source\Orket-Extensions\TextMystery`
2. Replay a short deterministic script:
   - time question
   - where question
   - access-list question
   - witness question
   - object/action question
3. Inspect transcript for:
   - no raw internal IDs (`FACT_`, `_PRESENT_AT_`)
   - at least one witness line
   - at least one presence line
   - at least one access list line with NPC names
4. Continue from PR6 tasks:
   - companion quality ranking pass
   - clarify text quality for place-scoped access prompts
5. If pausing gameplay and switching to SDK:
   - lock interfaces in `c:\Source\OrketSDK` for `manifest`, `capabilities`, `workload`, `result`, `testing`
   - wire TextMystery through SDK context/capability seams without changing gameplay semantics

### Known risk notes

1. A valid architecture does not guarantee play feel; current bottleneck is companion policy quality, not truth engine correctness.
2. Avoid broad SDK extraction during tuning unless code is proven generic across workloads.
3. Keep Gameplay Kernel semantics in TextMystery first; extract stabilized infrastructure to SDK in hardening slices.

## Non-Goals (Layer 0)

1. No scaffolder.
2. No generalized media pipeline framework.
3. No public `TurnResult` builders.
4. No expansion beyond minimal capability and artifact seams required by game slices.

## Exit Criteria

Layer 0 is complete when:
1. TextMystery runs as an SDK workload.
2. Gameplay semantics are upgraded (typed conversational facts, witness/presence chain, meaningful refusal overlap).
3. Audio output and optional audio input are capability-driven, not hardwired in game logic.
4. Artifact-first replay path exists for audio-related flows.
5. Orket integration changes are minimal and legacy-safe.
6. SDK package is standalone and versionable.
