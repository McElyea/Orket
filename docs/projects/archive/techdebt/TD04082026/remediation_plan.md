# Remediation Plan — Current-State Truth And UI Readiness

Last updated: 2026-04-08  
Status: Completed  
Closed: 2026-04-08  
Purpose: address the highest-value current code and behavioral seams before or alongside the first serious UI slice.

## Planning Principles

1. Fix truth seams before adding visual confidence.
2. Prefer narrow, verifiable slices over broad cleanup campaigns.
3. Separate runtime facts from UI projections.
4. Treat degraded behavior as first-class, not as an edge case.
5. Do not let the front end discover authority by spelunking raw artifacts.

## Sequencing Overview

```text
Phase 1 — Runtime truth
[W1] ODR role independence
[W2] Valid-round state advancement only
[W3] Explicit cards-runtime extraction status

Phase 2 — Behavioral truth
[W4] Action-surface truth cleanup
[W5] Session/context reset truth
[W6] Governed structured-output truth
[W7] Child-schema authority cleanup

Phase 3 — Evidence truth
[W8] Determinism language and proof cleanup
[W9] Human-facing outcome vocabulary

Phase 4 — UI readiness
[W10] Stable UI view models
[W11] Card Viewer/Runner first slice
```

---

## W1 — Make ODR role separation truthful

### Problem

Cards ODR currently risks presenting a two-role refinement loop while using the same model authority for architect and auditor.

### Implementation

1. Add explicit `auditor_client` support through the cards ODR path.
2. Preserve same-client fallback only for compatibility.
3. Emit a machine-readable role-independence flag:
   - `audit_mode: independent`
   - `audit_mode: self_audit_fallback`
4. Include this in the cards runtime facts summary.

### Acceptance

1. Independent architect/auditor execution is possible without patching internals.
2. Same-client fallback is explicitly recorded as degraded/compatibility behavior.
3. The UI can distinguish independent critique from self-audit without inference.

### Proof Target

- contract test
- integration test

---

## W2 — Advance active requirement state only from valid rounds

### Problem

Invalid rounds can currently mutate the next-round prompt baseline.

### Implementation

1. Only update active requirement state from valid rounds.
2. Preserve invalid parsed drafts as trace artifacts, not active state.
3. Emit both:
   - `last_valid_round_index`
   - `last_emitted_round_index`
4. Add explicit divergence assertion where needed.

### Acceptance

1. Invalid rounds do not become active prompt baseline.
2. Validity baseline and prompt baseline cannot silently diverge.
3. Telemetry makes any divergence impossible to hide.

### Proof Target

- unit test
- integration test

---

## W3 — Fail explicitly when cards-runtime fact extraction fails

### Problem

Cards-runtime summary extraction can currently collapse read failures into an empty result.

### Implementation

1. Replace empty-failure ambiguity with explicit resolution states:
   - `resolved`
   - `no_events_found`
   - `log_missing`
   - `resolution_failed`
2. Record extraction outcome in `run_summary`.
3. Keep raw error detail machine-readable when safe.

### Acceptance

1. Missing facts are never confused with extraction failure.
2. The UI can render a degraded badge with a stable reason.
3. Run summaries remain truthful even when log-derived enrichment fails.

### Proof Target

- contract test
- integration test

---

## W4 — Remove narrated pseudo-actions from supported action surfaces

### Problem

Actions like `adopt_issue` should not remain in the supported action surface if they only narrate.

### Implementation

1. Remove pseudo-actions from canonical supported-action registries.
2. Route them either to unsupported-action handling or to explicit proposal/suggestion surfaces.
3. Update help text, prompt text, and action-parity tests.

### Acceptance

1. No supported action claims execution without a real state transition.
2. UI action buttons map only to executable, auditable operations.

### Proof Target

- contract test
- integration test

---

## W5 — Make session reset truth observable and real

### Problem

`clear_context()` currently risks meaning more than it actually enforces on explicit-session backends.

### Implementation

1. Track provider session epoch for relevant backends.
2. Rotate or reset session identity on successful clear.
3. Emit session epoch and reset status in telemetry.
4. Mark non-resettable backends clearly.

### Acceptance

1. Post-clear requests do not silently reuse prior session identity where reset is claimed.
2. UI can display `fresh_context`, `context_unknown`, or `stateless_backend` truthfully.

### Proof Target

- contract test
- targeted adapter test

---

## W6 — Default governed UI-facing paths to strict structure

### Problem

A serious UI cannot sit on hidden compatibility JSON salvage.

### Implementation

1. Make governed driver/UI paths default to strict JSON or equivalent strict structured output.
2. Keep compatibility salvage as an explicit opt-in mode.
3. Surface parse mode in telemetry.

### Acceptance

1. UI-triggered governed runs are strict by default.
2. Compatibility mode is visible, deliberate, and degraded.

### Proof Target

- contract test
- integration test

---

## W7 — Canonicalize epic child schema to `issues`

### Problem

Dual `cards` / `issues` authority will poison the UI boundary.

### Implementation

1. Make `issues` the single canonical child key for all touched paths.
2. Normalize legacy `cards` payloads at the boundary only.
3. Remove dual-vocabulary UI/API exposure.

### Acceptance

1. UI and API docs expose only `issues`.
2. Touched create/read/write paths use one authority.

### Proof Target

- contract test
- integration test

---

## W8 — Clean up determinism language and proof classes

### Problem

Historical test/workflow surfaces have overstated determinism proof.

### Implementation

1. Rename weak checks honestly:
   - `comparator_identity_smoke`
   - `fixture_shape_consistency`
   - `single_run_smoke`
2. Reserve `deterministic` / `stability proven` language for real multi-run evidence over real artifacts.
3. Audit dashboards and workflow output fields.

### Acceptance

1. No green surface implies stronger proof than was actually performed.
2. UI can show “smoke passed” without calling it determinism proof.

### Proof Target

- workflow test
- artifact schema check

---

## W9 — Separate evidence completeness from lifecycle outcome

### Problem

Technical completeness fields like MAR/replay-ready can be misread as “successful work completed.”

### Implementation

1. Add human-facing lifecycle categories such as:
   - `prebuild_blocked`
   - `artifact_run_failed`
   - `artifact_run_completed_unverified`
   - `artifact_run_verified`
   - `degraded_completed`
2. Keep existing technical fields, but do not overload them.
3. Add a stable mapping from runtime facts to operator-facing labels.

### Acceptance

1. A prebuild-only stop cannot be mistaken for a verified artifact-producing success.
2. UI badges map from a canonical outcome vocabulary, not ad hoc frontend logic.

### Proof Target

- contract test
- UI view-model test

---

## W10 — Build stable UI view models before building broad UI chrome

### Problem

The raw runtime surface is too rich and too low-level for direct frontend binding.

### Implementation

Create explicit read models for:

1. `CardListItemView`
2. `CardDetailView`
3. `RunHistoryItemView`
4. `RunDetailView`
5. `ProviderStatusView`
6. `SystemHealthView`

Each should flatten only operator-useful fields and include:

- primary status
- degraded flag
- human-readable summary
- machine-readable reason codes
- next recommended action

### Acceptance

1. The front end does not need to parse artifact arrays to understand a run.
2. View models are stable, documented, and test-covered.

### Proof Target

- contract test
- API integration test

---

## W11 — Ship the Card Viewer/Runner as the first UI slice

### Scope

This should be the first serious tab because it is the closest thing Orket has to a primary work surface.

### MVP Surface

1. Card list with filters:
   - open
   - running
   - blocked
   - review
   - terminal failure
   - completed
2. Card detail panel with:
   - issue summary
   - execution profile
   - artifact contract
   - last run outcome
   - degradation badge
   - run button / rerun button
3. Run subpanel with:
   - stop reason
   - key artifacts
   - ODR state
   - provenance / verification summary
4. Explicit degraded-state callouts.

### Non-Goals

1. Full artifact explorer
2. All-proof dashboard
3. Every config surface in one page

### Acceptance

1. A user can select a card, run it, and understand the result without reading raw JSON.
2. No success badge or button implies more than the runtime actually knows.
3. Degraded behavior is shown as first-class product state.

### Proof Target

- UI integration test
- contract test over backing view models

---

## Release Rule

Do not add broad dashboard tabs until W1 through W10 are substantially in place.

The first UI should be:

- truthful,
- narrow,
- operator-centered,
- degradation-first.

Not pretty-first. Not dashboard-first. Not artifact-dump-first.

## Final Recommendation

The correct move is not “build the whole cockpit now.”

The correct move is:

1. fix the current truth seams,
2. create stable UI-facing read models,
3. ship the Card Viewer/Runner,
4. then expand outward tab by tab.
