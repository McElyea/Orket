# Extension SDK v0 Implementation Plan

Last updated: 2026-02-28

## Strategy

1. SDK contracts and helpers first (standalone package).
2. Runtime adapter path for SDK workloads (dual-path bridge).
3. Legacy `RunPlan` extension execution preserved during transition.
4. Reference workload (TextMystery) proves the seam works.
5. Second workload (Meta Breaker) proves the seam is generic.

---

## What's Done

### Gameplay Kernel (TextMystery -- see `04-TEXTMYSTERY-LAYER0.md`)

All gameplay-kernel foundational work is substantially complete:
- Typed facts with `kind` for all 7 payload shapes
- Discovery/unlock model with namespaced keys
- Resolver dynamic-first deterministic matching
- Companion policy upgrades (repeat suppression, NPC-aware routing, witness-chain-first)
- Disambiguation UX seam
- First-person render for speaker-owned facts
- Local deterministic test suite green

### Reforger Compiler

- Normalize > mutate > evaluate > score > materialize pipeline complete
- TextMystery route (`TextMysteryPersonaRouteV0`) implemented
- Scenario pack format, patch surface enforcement, SHA manifests
- Determinism tests passing

---

## What Remains

### Phase 1: SDK Package Bootstrap (next)

Status: **complete**

Deliverables:
1. Create `c:\Source\OrketSDK` with package structure
2. Implement `orket_extension_sdk.manifest` -- Manifest model, load, validate
3. Implement `orket_extension_sdk.capabilities` -- CapabilityId, CapabilityProvider, CapabilityRegistry, interfaces
4. Implement `orket_extension_sdk.workload` -- WorkloadContext, Workload protocol
5. Implement `orket_extension_sdk.result` -- WorkloadResult, ArtifactRef, Issue
6. Implement `orket_extension_sdk.testing` -- FakeCapabilities, DeterminismHarness, GoldenArtifact
7. Unit tests for each module

Exit criteria:
- SDK package imports cleanly with minimal surface
- Contract models and validation tests pass
- `pip install -e c:\Source\OrketSDK` works in both Orket and TextMystery environments

Progress update (2026-02-28):
- Added in-repo SDK bootstrap package at `orket_extension_sdk/`
- Implemented:
  - `manifest.py` (`ExtensionManifest`, `WorkloadManifest`, `load_manifest`)
  - `capabilities.py` (`CapabilityId`, `CapabilityProvider`, `CapabilityRegistry`)
  - `workload.py` (`WorkloadContext`, `Workload`, `run_workload`)
  - `result.py` (`WorkloadResult`, `ArtifactRef`, `Issue`)
  - `testing.py` (`FakeCapabilities`, `DeterminismHarness`, `GoldenArtifact`)
- Added unit tests under `tests/sdk/`:
  - `test_manifest.py`
  - `test_capabilities.py`
  - `test_workload.py`
  - `test_result.py`
  - `test_testing.py`
- Validation: `python -m pytest -q tests/sdk` -> `16 passed`
- Latest validation: `python -m pytest -q tests/sdk` -> `16 passed` (still green after runtime/bridge expansion)

### Phase 2: Runtime Dual-Path Bridge

Status: **complete**

Deliverables:
1. Runtime detection of extension contract style (legacy vs SDK v0)
2. SDK run path: manifest parse > capability preflight > WorkloadContext construction > workload invocation > WorkloadResult validation
3. Internal mapping from WorkloadResult into engine runtime internals
4. Legacy RunPlan path unchanged

Exit criteria:
- SDK workload runs end-to-end in Orket runtime
- Legacy workload runs unchanged
- Missing capability errors are deterministic and actionable

Progress update (2026-02-28):
- Added contract-style routing in `orket/extensions/manager.py`:
  - legacy `RunPlan` path preserved
  - SDK v0 `run(ctx, input) -> WorkloadResult` path added
- Added manifest-style detection at install time:
  - legacy `orket_extension.json`
  - SDK `extension.yaml` / `extension.yml` / `extension.json`
- Added SDK workload metadata support in extension catalog/runtime records:
  - `contract_style`, `entrypoint`, `required_capabilities`, `manifest_path`
- Added SDK preflight and execution mechanics:
  - capability preflight (`E_SDK_CAPABILITY_MISSING`, fail-closed)
  - SDK context construction
  - artifact path confinement + digest checks for declared artifacts
  - SDK provenance emission and artifact manifest emission
- Added runtime coverage in `tests/runtime/test_extension_manager.py`:
  - SDK install/registration
  - SDK JSON-manifest install coverage
  - SDK workload execution with artifacts + provenance
  - missing-capability deterministic failure
  - mixed-catalog execution (legacy + SDK v0)

### Phase 3: TextMystery SDK Integration

Status: **complete**

Deliverables:
1. Add `extension.yaml` to TextMystery using SDK manifest schema
2. Replace direct provider creation with capability-based retrieval
3. Write transcript and summary through SDK artifact writer
4. Emit trace events for key phases
5. Verify deterministic replay through SDK harness

Exit criteria:
- TextMystery runs as an SDK workload under Orket
- All existing parity/leak/determinism tests remain green
- Artifacts include digest metadata

Progress update (2026-02-28):
- Migrated bridge extension registration script to SDK v0 outputs:
  - `scripts/register_textmystery_bridge_extension.py` now writes `extension.yaml`
  - generated bridge module now exposes SDK entrypoint `run_workload(ctx, input)`
  - generated workload now emits `WorkloadResult` with digest-verified `bridge_response.json` artifact
- Updated generated catalog row to SDK metadata (`contract_style`, `entrypoint`, `required_capabilities`)
- Added coverage in `tests/application/test_register_textmystery_bridge_extension.py` for manifest + catalog shape
- Upgraded bridge runtime to direct local contract invocation (no HTTP dependency):
  - workload now imports TextMystery contract functions from `<textmystery_root>/src`
  - parity runs also emit `turn_results.json` digest artifact
  - output includes trace-phase markers for contract-call start/complete
- Added deterministic replay coverage for bridge SDK workload:
  - `tests/application/test_textmystery_bridge_sdk_runtime.py`
- Added real local smoke evidence through Orket SDK path:
  - `python scripts/run_textmystery_easy_smoke.py --textmystery-root C:/Source/Orket-Extensions/TextMystery`
  - latest run result: `RESULT=PASS`

### Phase 4: Meta Breaker Route (proves SDK is generic)

Status: **complete**

Deliverables:
1. Define Meta Breaker as a reforger route (rule validation for card games)
2. Build toy TCG rule system (30-50 cards, 3 archetypes, simple mana/combat)
3. Meta Breaker workload: `run(ctx, input) -> WorkloadResult` with win rate analysis
4. Scenario packs for balance validation (first-player advantage, dominant strategies, infinite loops)
5. Prove SDK contracts work for a non-TextMystery workload

Exit criteria:
- Meta Breaker runs as an SDK workload
- Reforger can mutate game rules and score balance outcomes
- SDK required zero game-specific changes to support this

Progress update (2026-02-28):
- Added Meta Breaker SDK extension bootstrap scripts:
  - `scripts/register_meta_breaker_extension.py`
  - `scripts/run_meta_breaker_workload.py`
- Added deterministic non-TextMystery SDK workload implementation (archetype matchup analysis + digest artifact output)
- Added scenario pack runner for balance checks:
  - `scripts/run_meta_breaker_scenarios.py`
  - predefined scenarios for first-player advantage and strict balance threshold
- Added Reforger route + compile mode for Meta Breaker:
  - route: `meta_breaker_v0` (`orket/reforger/routes/meta_breaker_v0.py`)
  - compiler mode: `meta_balance` with deterministic scoring checks
  - coverage: `tests/reforger/compiler/test_compile_meta_breaker_v0.py`
- Added coverage:
  - `tests/application/test_register_meta_breaker_extension.py`
  - `tests/application/test_run_meta_breaker_workload.py`
  - `tests/application/test_run_meta_breaker_scenarios.py`
- Expanded toy TCG workload model:
  - 30-card deterministic pool (10 per archetype: aggro/control/combo)
  - dominance + loop-risk checks and scenario-pack execution

### Phase 5: Documentation and Deprecation Gates

Status: **complete**

Deliverables:
1. Public docs updated to SDK v0 seam language
2. Extension author guide ("build a workload in 10 minutes")
3. Migration note for legacy path with deprecation readiness criteria
4. Explicit statement: TurnResult is internal-only

Exit criteria:
- Single clear public extension story in docs
- No public docs instruct direct engine/turn internals usage

Progress update (2026-02-28):
- Added extension author quickstart guide: `05-AUTHOR-GUIDE.md`
- Updated `README.md` SDK document index to include author guide
- `TurnResult` internal-only policy remains explicit in SDK README and migration docs
- Added explicit legacy migration note and checklist: `06-LEGACY-MIGRATION-NOTE.md`

### Phase 6: Hardening

Status: **complete**

Deliverables:
1. Deterministic hint/disambiguation policy conformance tests (TextMystery-specific)
2. Security audit of artifact write confinement
3. Performance baseline for workload execution

Exit criteria:
- Demo workloads do not exhibit repeated suggestion loops
- Artifact path traversal blocked
- Execution latency baselined

Progress update (2026-02-28):
- Added SDK runtime hardening tests in `tests/runtime/test_extension_manager.py`:
  - artifact path escape attempt rejected (`E_SDK_ARTIFACT_ESCAPE`)
  - artifact digest mismatch rejected (`E_SDK_ARTIFACT_DIGEST_MISMATCH`)
- Added workload execution latency baseline runner:
  - script: `scripts/run_extension_workload_baseline.py`
  - report schema includes min/max/mean/p50/p95 latency and per-run provenance roots
  - coverage: `tests/application/test_run_extension_workload_baseline.py`
- Added TextMystery policy conformance gate runner:
  - script: `scripts/run_textmystery_policy_conformance.py`
  - runs hint/disambiguation conformance tests in external TextMystery repo and emits JSON report
  - coverage: `tests/application/test_run_textmystery_policy_conformance.py`
- Validation evidence:
  - `python scripts/run_textmystery_policy_conformance.py --textmystery-root C:/Source/Orket-Extensions/TextMystery --output workspace/diagnostics/textmystery_policy_conformance.latest.json`
  - latest run result: pass (`7 passed`)

---

## Remaining TextMystery Polish (can run in parallel)

These are gameplay quality items, not SDK blockers:
1. Companion quality pass (cross-suspect handoff, ranking)
2. Clarify UX quality (place-scoped access clarifications)
3. Tone/variation pass (DONT_KNOW/REFUSE phrase pools)

See `04-TEXTMYSTERY-LAYER0.md` for details.

---

## Test Strategy

### SDK contract tests
- Manifest parse/validate (YAML and JSON)
- Required field errors with stable issue codes
- Capability registry behavior and preflight
- WorkloadResult model validation
- Artifact path confinement

### SDK determinism tests
- DeterminismHarness stable output + artifact digest comparisons
- GoldenArtifact snapshot assertions

### Integration tests
- TextMystery as SDK workload via Orket bridge
- Meta Breaker as SDK workload via Orket bridge
- Legacy extension path still works
- Mixed catalog execution (legacy + v0)

### Workload-specific tests
- TextMystery: parity, leak, transcript quality (owned by TextMystery project)
- Meta Breaker: balance detection, loop detection, dominance detection (owned by Meta Breaker project)

---

## Risks

1. **Dual-surface confusion during transition** -- mitigate by routing all docs to SDK seam first
2. **Determinism drift from environment-specific output** -- mitigate with digest-based checks and noise normalization
3. **SDK over-extraction** -- mitigate by requiring two workloads (TextMystery + Meta Breaker) before generalizing
4. **Scope creep into game design** -- mitigate by keeping gameplay decisions in workload projects, not SDK
