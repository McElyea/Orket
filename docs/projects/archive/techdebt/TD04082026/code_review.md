# Brutal Code Review — Orket UI / Cards / ODR Slice

Last updated: 2026-04-08  
Basis: static review of the uploaded `project_dump.txt`, sampled code snippets, current archived techdebt reviews, and current cards/ODR artifacts.  
Method: code-and-artifact review only. I did not execute the repo.

## Executive Summary

The good news is that Orket is no longer in the broad “everything is behaviorally suspect” state reflected by older reviews. A substantial amount of baseline cleanup was already closed out in archived techdebt work.

The bad news is that the current Cards / ODR slice still contains several high-leverage seams that would make a UI dishonest unless they are fixed or explicitly quarantined.

The biggest current code-level problem is this:

**Cards ODR is structurally wired in a way that can look rigorous while failing to produce real adversarial refinement.**

That matters because a UI will magnify the illusion. Once you put rounds, badges, stop reasons, and “verified” states on screen, weak internals stop being harmless implementation debt and become user-facing lies.

## What Is Strong

1. The runtime is already producing a real machine-readable surface around runs: `run_summary`, `cards_runtime`, artifact contracts, packet/provenance blocks, and stop reasons exist as data rather than prose.
2. There is already explicit UI-related governance in the repo: `ui_lane_security_boundary_test_contract` and `degradation_first_ui_standard` appear in current runtime/contract surfaces.
3. The cards runtime contract has named execution profiles and default output paths, which is exactly the kind of stable backbone a UI needs.
4. Current test and review material shows the project has already done meaningful cleanup rather than just accumulating complaints.

## Critical Findings

### 1. ODR architect and auditor are effectively the same authority

The current cards ODR integration passes the same model client as both architect and auditor. That makes the refinement loop look adversarial while actually being self-review. In practice, this risks fast “stability” without real challenge.

Why this is severe:

- It undermines the core claim of iterative refinement.
- It creates false confidence in stop reasons like stability or max rounds.
- A future UI would almost certainly overstate what happened by visualizing “rounds” as if there were two independent roles.

What to do:

- Add an explicit `auditor_client` lane.
- Default it safely for compatibility, but treat same-client self-audit as degraded, not normal.
- Expose this in telemetry so the UI can show `self_audit=true` versus `independent_audit=true`.

### 2. The live runner updates working requirement state from invalid rounds

The live ODR runner updates the current requirement even when a round parsed successfully but failed semantic validity. That means the next prompt can be based on a degraded requirement while the validity logic still treats the previous valid round as the baseline.

Why this is severe:

- Prompt state and evaluation state can diverge.
- Demotion detection becomes less trustworthy.
- The UI could show a clean round history while the actual loop state is already incoherent.

What to do:

- Only advance current working requirement from valid rounds.
- Emit both `last_valid_round` and `last_emitted_round` if you need both concepts.
- Make divergence impossible or explicitly observable.

## High Findings

### 3. Cards runtime facts are reconstructed from logs and fail soft

The cards runtime summary resolver scans `orket.log`, filters selected events, and silently returns `{}` on missing log files or `OSError`. This is pragmatic, but it means cards facts can disappear without a hard failure.

Why this is dangerous:

- Missing cards facts can look like “no facts” instead of “fact extraction failed.”
- A UI built on this will eventually show blank cards metadata with no trustworthy reason.
- Runtime truth becomes dependent on secondary log availability instead of a first-class ledger surface.

What to do:

- Distinguish `no_cards_runtime_events` from `cards_runtime_resolution_failed`.
- Put a stable failure token in `run_summary` when extraction fails.
- Do not let the UI infer absence from extraction failure.

### 4. ODR-only runs are accepted as replay-ready / MAR-complete with zero turn capture

Current contract tests accept an ODR-only run surface as MAR complete and replay ready even when turn count is zero.

This may be internally reasonable, but it is a UI trap.

Why it matters:

- Users will read “complete” and “replay ready” as “this run did real work.”
- An ODR-prebuild stop can be a valid terminal result, but it is not equivalent to a successful artifact-producing run.

What to do:

- Split completion surfaces into at least:
  - `prebuild_only`
  - `artifact_attempted`
  - `artifact_verified`
- Keep MAR/replay signals, but never let them collapse lifecycle meaning.

### 5. The repo still carries action-surface truth debt around driver operations

Archived current-state behavioral review material still shows `adopt_issue` being advertised as an action surface while only returning narration, plus an active cleanup plan around that exact seam.

Why this matters for UI:

- You cannot put a button on a narrated pseudo-action.
- A UI action surface must map only to real state transitions or explicit suggestions.

What to do:

- Remove narrated pseudo-actions from interactive UI surfaces.
- Only surface them as “proposed action” text until they are actually implemented.

### 6. Session reset truth is still questionable for explicit-session backends

The archived behavioral current-state review also shows a seam where `clear_context()` is called by orchestration while explicit session identifiers are still attached on some local-model/openai-compatible paths.

Why this matters for UI:

- The UI will encourage repeated runs and comparisons.
- If “new run” does not actually mean clean session state, the UI becomes an amplifier for hidden carryover.

What to do:

- Expose session epoch / context reset state as telemetry.
- Add a visible “fresh context” bit to run metadata.
- Treat unknown-reset status as degraded.

## Medium Findings

### 7. Compatibility JSON slicing is still the wrong default story for governed paths

Archived behavioral work shows a live cleanup lane around governed driver paths defaulting to strict JSON instead of compatibility slicing from first brace to last brace.

Why this matters:

- A UI runner needs predictable structured responses.
- Compatibility slicing is okay as an escape hatch, not as the hidden default under a governed experience.

What to do:

- UI paths should require strict structured surfaces.
- Compatibility mode should be clearly labeled and explicitly operator-selected.

### 8. The run surface is rich, but too raw for direct UI binding

Current `run_summary` surfaces already include artifact IDs, cards runtime facts, packet/provenance data, runtime vocabularies, and many governance contracts. This is good for auditability and bad for naive UI binding.

Why this matters:

- A one-page widget dashboard will collapse under the weight of the raw surface.
- The UI needs curated view models, not direct JSON dumping.

What to do:

- Add server-side view-model endpoints or adapters for:
  - card list row
  - card detail
  - run history row
  - run comparison
  - provider status row
- Never make the front end discover meaning by reading artifact arrays.

### 9. `cards` versus `issues` schema drift is poison for UI work

Archived behavioral implementation planning still treats canonicalization of epic child schema to `issues` as an active truth seam.

Why this matters:

- A UI cannot survive dual child vocabularies for the same concept.
- The front end will inevitably pick one, and the backend will punish it later.

What to do:

- Pick `issues` as canonical.
- Normalize legacy data at the boundary.
- Never expose both names to UI consumers.

## Low Findings

### 10. UI-related standards exist, but they are not yet product surfaces

The current repo includes UI security-boundary and degradation-first contracts, which is excellent. But that does not yet equal a shippable UI architecture.

What is still missing:

- stable UI-facing read models
- explicit tab ownership boundaries
- degradation vocabulary tuned for humans rather than proof artifacts
- a first-class concept of “what the operator should do next”

## Bottom Line

The repo is finally at the point where a UI makes sense, but only if it is built around truthful, purpose-specific tabs and not around raw artifact inspection.

The current Cards / ODR slice is close enough to support a first UI, but not honest enough to support a glossy one.

The rule should be:

**Do not ship visual confidence before you ship runtime truth.**

That means:

1. Fix ODR role independence.
2. Fix invalid-round state advancement.
3. Fail explicitly when cards-runtime fact extraction fails.
4. Separate prebuild-only outcomes from artifact-producing outcomes.
5. Canonicalize schema and action surfaces before exposing them as controls.

Once those are done, a tabbed UI becomes an accelerator instead of a lie amplifier.
