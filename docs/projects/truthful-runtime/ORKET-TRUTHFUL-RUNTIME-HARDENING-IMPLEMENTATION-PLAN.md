# Orket Truthful Runtime Hardening Implementation Plan

Last updated: 2026-03-14
Status: Staged / Waiting (Phase C implementation and Phases D-E)
Owner: Orket Core
Lane type: Staged / Waiting (externally gated by proof availability)
Canonical staged-lane authority: This file owns detailed reentry criteria for this lane.
Accepted Phase C requirements lane:
1. `docs/projects/truthful-runtime/TRH03142026-PHASE-C-REQUIREMENTS.md`
Active bounded Phase C packet-1 implementation plan:
1. `docs/projects/truthful-runtime/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`
Primary input: operator-provided control-surface backlog (runtime truth, routing truth, provenance, conformance, and promotion hardening)
Related authority inputs:
1. `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`
2. `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
3. `docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md`
4. `docs/specs/PROTOCOL_ERROR_CODE_REGISTRY.md`
5. `docs/specs/RUNTIME_INVARIANTS.md`
6. `docs/TESTING_POLICY.md`

## 1. Objective

Make Orket routing and runtime behavior auditable, attributable, and promotion-safe by replacing assumption-driven behavior with explicit capability truth, deterministic contracts, and evidence-gated promotion.

Wave 2 closeout archive:
1. `docs/projects/archive/future/TRH03102026-WAVE2-CLOSEOUT/ORKET-TRUTHFUL-RUNTIME-HARDENING-WAVE-2-IMPLEMENTATION-PLAN.md`

## 2. Scope

In scope:
1. capability truth contracts for tools/providers/models
2. execution provenance and repair/fallback observability
3. deterministic routing/prompt/tool policy surfaces
4. session/run/tool/voice/UI state and degradation semantics
5. conformance-first verification and promotion gates

Out of scope:
1. net-new model/provider integration features not required for truth contracts
2. UI redesign unrelated to truth/degradation language
3. broad runtime refactors not required to enforce defined contracts

## 3. Phase Plan

Phase-specific implementation plans:
1. `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-C-IMPLEMENTATION-PLAN.md`
2. `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-D-IMPLEMENTATION-PLAN.md`
3. `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-E-IMPLEMENTATION-PLAN.md`

Phase closeout archives:
1. `docs/projects/archive/future/TRH03102026-PHASE-A-CLOSEOUT/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-A-IMPLEMENTATION-PLAN.md`
2. `docs/projects/archive/future/TRH03102026-PHASE-B-CLOSEOUT/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-B-IMPLEMENTATION-PLAN.md`
3. `docs/projects/archive/future/TRH03102026-WAVE2-CLOSEOUT/ORKET-TRUTHFUL-RUNTIME-HARDENING-WAVE-2-IMPLEMENTATION-PLAN.md`

## Phase A - Contract and Vocabulary Freeze

Deliverables:
1. capability registry contract (tool/provider/model capability advertisement)
2. provider truth table contract (streaming/JSON/tools/image/seed/context/repair tolerance)
3. canonical run phase contract (`input_normalize -> route -> render_prompt -> execute -> validate -> repair -> finalize -> persist -> emit_observability`)
4. fail-open vs fail-closed registry by subsystem
5. degradation taxonomy and runtime vocabulary freeze
6. timeout semantics and streaming semantics contracts
7. state transition registry baseline (sessions/runs/tools/voice/UI)
8. event ordering and atomic finalize contract
9. error-code alignment for user-visible failures

Acceptance:
1. every runtime status/error term used in code is in a canonical vocabulary source
2. run phase order is explicit and mechanically testable
3. hard-stop vs degrade behavior is explicit per subsystem

## Phase B - Routing, Prompting, and Tool Policy Truth

Deliverables:
1. router decision artifact (compact route-why explanation)
2. prompt profile versioning and rendering rule contract
3. tool invocation eligibility contract by run type
4. deterministic mode flag (heuristics/retries/fallback reduced to required minimum)
5. model profile BIOS contract (provider-model strictness/repair/hazard profile)
6. local-vs-remote route policy contract
7. human override lane (route/prompt/strictness)
8. capability probation and regression quarantine policies

Acceptance:
1. route selection is explainable per run
2. prompt behavior is attributable to versioned profile artifacts
3. model/tool behavior cannot exceed declared policy envelope

## Phase C - Provenance, Repair, and Fallback Truth

Deliverables:
1. execution provenance envelope (model/provider/profile/tool/retry/repair/fallback stamps)
2. structured repair ledger contract (reason, strategy, disposition)
3. response truth classification (`direct|inferred|estimated|repaired|degraded`)
4. narration-to-effect audit path
5. silent fallback detector and defect classification
6. cancellation truth path and idempotency key contract
7. source attribution contract and evidence-first mode for high-stakes lanes
8. voice truth contract (text/TTS generation/playback/lip-sync distinctions)
9. artifact generation provenance contract (docs/sheets/slides metadata)

Acceptance:
1. each run emits provenance and truth classification artifacts
2. silent fallback is machine-detectable and reportable
3. repairs and retries are visible and attributable

## Phase D - Memory and Trust Policies

Deliverables:
1. session memory policy contract (working vs durable vs reference context)
2. memory write threshold policy and rationale requirement
3. memory conflict resolution contract (contradiction/staleness/user correction)
4. tool result trust-level contract (`authoritative|advisory|stale_risk|unverified`)

Acceptance:
1. memory mutation behavior is policy-bound and explainable
2. trust level is explicit before synthesis in configured lanes

## Phase E - Conformance, Promotion, and Operational Governance

Deliverables:
1. behavioral contract test suite (user-visible truth)
2. false-green checklist and standing hunt process
3. golden transcript suite with controlled diffing
4. user expectation alignment tests (`saved/synced/used memory/searched/verified`)
5. operator sign-off artifact for promotions
6. evidence-based promotion gate policy
7. operational scorecard contract (correctness/degradation/repair/latency/conformance/trust)
8. repo introspection mode report contract
9. spec debt backlog structure (docs/schemas/tests/runtime mismatch)
10. short canonical philosophy document

Acceptance:
1. promotion requires repeated evidence, not single-run success
2. release scorecard includes trust and conformance metrics
3. expectation-alignment checks block misleading claims

## 4. Execution Order

Completed:
1. Phase A (`docs/projects/archive/future/TRH03102026-PHASE-A-CLOSEOUT/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-A-IMPLEMENTATION-PLAN.md`)
2. Phase B (`docs/projects/archive/future/TRH03102026-PHASE-B-CLOSEOUT/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-B-IMPLEMENTATION-PLAN.md`)

Remaining strict order:
1. Phase C packet-1 implementation
2. remaining Phase C backlog if explicitly reopened
3. Phase D
4. Phase E

Current staging state:
1. Accepted requirements definition for the bounded first Phase C packet lives in `docs/projects/truthful-runtime/TRH03142026-PHASE-C-REQUIREMENTS.md`.
2. Active bounded packet-1 implementation now lives in `docs/projects/truthful-runtime/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`.
3. This staged lane now governs only remaining Phase C backlog beyond packet-1 plus later Phase D-E work.
4. Phase C-E are not marked complete because phase-level completion proof is not yet established.

Critical path:
`C -> E`

Rationale:
1. vocabulary/contracts and routing/prompt/tool policy baselines are complete from Phases A/B.
2. provenance and fallback truth must exist before evidence-gated promotion is meaningful.

## 5. Staging and Reentry Authority

This file is the canonical reentry authority for this staged lane. The roadmap entry stays terse; detailed reentry criteria and remaining-proof status live here.

Why staged now:
1. Phase A, Phase B, and Wave 2 closeout artifacts exist, but Phase C-E do not have accepted phase-level completion proof.
2. Provenance and fallback truth remain the critical path before memory/trust policy work or promotion-governance work should resume.
3. Broad product expansion work is not a valid reason to reopen this lane.

Missing proof before broad reentry:
1. No accepted Phase C packet yet proves execution provenance, visible repair/fallback behavior, and truth classification as implemented behavior.
2. No accepted Phase D packet yet proves policy-bound memory mutation and trust-level synthesis behavior.
3. No accepted Phase E packet yet proves conformance and promotion evidence gates on top of proven Phase C and Phase D behavior.

Smallest acceptable reentry slice:
1. Reenter at Phase C only.
2. Keep the first packet bounded to execution provenance envelope, response truth classification, silent fallback detection, and the proof work needed to verify those surfaces.
3. Do not include net-new UI work, enterprise auth/admin surfaces, packaging work, or unrelated provider expansion in the first packet.
4. Do not reopen Phase D or Phase E until the selected Phase C packet has acceptance proof.

Required evidence to reopen:
1. Completion or explicit stop of the active packet-1 implementation plan.
2. An explicit request naming the next Phase C slice as the target.
3. A bounded deliverable list taken from accepted requirements or a later accepted scope update, not from the full future backlog.
4. Named exit artifacts for the reopened slice.
5. Explicit non-goals so scope does not expand into adjacent product work.

## 6. Initial Reentry Slice (Recommended)

Recommended first packet:
1. execution provenance envelope
2. response truth classification (`direct|inferred|estimated|repaired|degraded`)
3. silent fallback detector and defect classification
4. contract/integration/end-to-end proof covering the above surfaces

Exit criteria:
1. each covered run emits provenance and truth classification artifacts
2. at least one silent fallback path is machine-detectable and reportable
3. repaired or degraded behavior is visible and attributable in proof artifacts

## 7. Verification Standards

Required:
1. contract tests for every new runtime vocabulary and phase/state contract
2. integration tests for provenance, fallback visibility, and cancellation truth
3. end-to-end behavioral tests for user-visible claims
4. golden transcript diff evidence for behavior-changing lanes

Truth-reporting rule:
1. no compile-only or mock-only evidence may be presented as runtime conformance proof

## 8. Risks and Mitigations

1. Risk: contract sprawl without executable adoption.
   1. Mitigation: each phase has bounded slice + acceptance gates.
2. Risk: over-instrumentation cost.
   1. Mitigation: compact artifacts, sampling rules, and scoped verbosity modes.
3. Risk: deterministic mode becomes stale.
   1. Mitigation: include deterministic mode in standing conformance suite.
4. Risk: promotion gates bypassed during pressure.
   1. Mitigation: require operator sign-off artifact for profile promotion.

## 9. Appendix A - Backlog Coverage Map

| Backlog Item | Phase |
|---|---|
| Capability registry | A |
| Provider truth table | A |
| Execution provenance envelope | C |
| Fail-open vs fail-closed registry | A |
| Router decision artifact | B (minimum in T1) |
| Prompt profile versioning | B |
| Canonical run phases | A |
| Tool invocation policy contract | B |
| Structured repair ledger | C |
| Response truth classification | C |
| Deterministic mode flag | B (minimum in T1) |
| Narration-to-effect audit | C |
| Silent fallback detector | C |
| Behavioral contract tests | E |
| False-green test hunt | E |
| Golden transcript suite | E |
| Degradation taxonomy | A |
| Schema authority map | A/E |
| Cross-spec consistency checker | E |
| State transition registry | A |
| Timeout semantics contract | A |
| Cancellation truth path | C |
| Idempotency keys everywhere | C |
| Event ordering rules | A |
| Atomic finalize path | A/C |
| Session memory policy | D |
| Memory write thresholds | D |
| Memory conflict resolution | D |
| Tool result trust levels | D |
| Evidence-first answer mode | C |
| Source attribution contract | C |
| Model profile BIOS | B |
| Capability probation lane | B |
| Regression quarantine | B |
| Local vs remote route policy | B |
| Human override lane | B |
| Operator sign-off artifact | E |
| Promotion gates by evidence | E |
| Spec debt backlog | E |
| Runtime vocabulary freeze | A |
| Error code discipline | A |
| UI degradation language | E |
| Voice truth contract | C |
| Streaming semantics | A |
| Artifact generation contract | C |
| Workspace hygiene rules | E |
| Repo introspection mode | E |
| Operational scorecard | E |
| User expectation alignment tests | E |
| Philosophy document | E |
