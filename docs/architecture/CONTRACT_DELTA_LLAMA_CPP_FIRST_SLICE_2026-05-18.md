# Contract Delta - llama.cpp First-Slice Local Provider Lane

## Summary
- Change title: Admit llama.cpp first-slice implementation lane without provider promotion
- Owner: Orket Core
- Date: 2026-05-18
- Affected contract(s): `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`

## Delta
- Current behavior: `llama.cpp` was documented only as a future compatibility lane under the local-prompting runtime compatibility matrix.
- Proposed behavior: `llama.cpp` has an accepted implementation path for exactly one Qwen-family GGUF profile, while runtime provider promotion remains blocked until promotion-readiness gates pass.
- Why this break is required now: The user explicitly requested moving the accepted llama.cpp requirements into a live lane and making the implementation plan the active roadmap priority. The implementation request was accepted on 2026-05-18, but provider support remains unpromoted until live GGUF proof passes.

## Migration Plan
1. Compatibility window: No runtime compatibility change is admitted by this delta; existing providers remain unchanged until implementation lands and is proven.
2. Migration steps: Update the local-prompting contract with the accepted first-slice boundaries, create the implementation plan, and track the lane through `docs/ROADMAP.md`.
3. Validation gates: Documentation hygiene must pass now; implementation proof must prove provider token validation, model inventory, source verification against `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/llama_cpp_first_target_model_source_verification_2026-05-18.json`, `/v1/models` preflight, `render_observability_classification=message_payload_audited` or rendered-prompt audit evidence, strict JSON smoke, tool-call smoke, streaming smoke or explicit `not_applicable`, and promotion-readiness regeneration before any promoted-profile claim.

## Rollback Plan
1. Rollback trigger: The first target model or llama.cpp server path proves unworkable before implementation begins.
2. Rollback steps: Move the roadmap entry back to Future Lanes, restore the contract row to future-only status, and mark the implementation plan paused or retired with the blocker.
3. Data/state recovery notes: No runtime state or provider artifacts are created by this documentation-only delta.

## Versioning Decision
- Version bump type: Contract clarification without runtime API admission.
- Effective version/date: 2026-05-18.
- Downstream impact: Contributors may plan the llama.cpp first slice, but may not claim runtime support until live proof gates pass.
