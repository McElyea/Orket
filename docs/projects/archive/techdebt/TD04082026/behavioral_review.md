# Behavioral Review — Orket Current-State Truth Seams

Last updated: 2026-04-08  
Basis: static review of the uploaded `project_dump.txt`, archived current-state behavioral truth review material, cards/ODR snippets, and current run-summary surfaces.  
Method: behavioral review only. I did not execute the repo.

## Executive Summary

The repo is not broadly behaviorally untrustworthy anymore. The older “everything lies” posture is out of date.

What remains is a concentrated set of behavioral seams that matter a lot because they sit directly on operator-facing paths:

- action surfaces
- context/session reset semantics
- structured-output truth
- cards / ODR lifecycle truth
- determinism proof truth

These are exactly the seams a UI would elevate from subtle engineering debt into visible product behavior.

## Behavioral Findings

### 1. `adopt_issue` is still message-as-action

What it claims:
- The driver action surface treats `adopt_issue` like a supported structural action.

What it does:
- It formats and returns narration instead of performing an actual structural move.

Why this is behaviorally wrong:
- Supported action implies a real state transition.
- Narration-only output is not an action.

Required correction:
- Either implement the mutation for real, with persistence and auditability, or remove it from the canonical supported action surface.

### 2. `clear_context()` can imply a reset that did not happen

What it claims:
- The orchestrator awaits `provider.clear_context()` in a way that strongly implies turn-to-turn session reset.

What it does:
- Archived current-state review material shows explicit session identifiers being attached on some backends while `clear_context()` remains a no-op for that path.

Why this is behaviorally wrong:
- “Clear” means reset. If explicit session identity survives, the name is lying.
- The user, operator, and future UI will assume run isolation that may not exist.

Required correction:
- Make reset real for explicit-session backends, or rename/remove the abstraction so nothing claims isolation that is not being enforced.

### 3. Governed paths still have compatibility-mode truth debt

What it claims:
- The driver is a JSON-disciplined governed surface.

What it does:
- Archived behavioral review material shows compatibility mode still accepting non-JSON by slicing from the first brace to the last brace on some paths.

Why this is behaviorally wrong:
- “Governed JSON” and “best-effort text salvage” are different contracts.
- Hidden salvage makes success look cleaner than it really is.

Required correction:
- Governed paths default to strict JSON.
- Compatibility salvage must be explicit, opt-in, and visibly labeled.

### 4. ODR self-audit can look like independent refinement

What it claims:
- Cards ODR appears to be a multi-round architect/auditor refinement process.

What it does:
- Current snippets show the same model client being used for both roles in the cards ODR path.

Why this is behaviorally wrong:
- Same-client self-review is not equivalent to independent challenge.
- Round counts and stop reasons can visually suggest rigor without the underlying adversarial structure.

Required correction:
- Separate architect and auditor authorities.
- Mark same-client fallback as degraded or compatibility mode.

### 5. Invalid rounds can still mutate the next-round baseline

What it claims:
- ODR validity machinery implies the loop advances from a trustworthy baseline.

What it does:
- Current review material shows the live runner updating `current_requirement` from parsed-but-invalid rounds.

Why this is behaviorally wrong:
- The model can be prompted with an invalid draft while semantic checks still reason from the last valid draft.
- Internal loop truth diverges even if the round log looks orderly.

Required correction:
- Only valid rounds advance the active requirement baseline.
- If invalid drafts are preserved, preserve them as trace artifacts, not active state.

### 6. Missing cards runtime facts can be mistaken for absent facts

What it claims:
- `run_summary` and derived cards facts describe the run.

What it does:
- The resolver can return `{}` on missing log or read error while treating that as a normal empty result surface.

Why this is behaviorally wrong:
- “No facts were present” is different from “fact extraction failed.”
- A UI will otherwise show silence where it should show degraded truth.

Required correction:
- Emit explicit extraction status.
- Preserve failure reason in machine-readable run metadata.

### 7. ODR-only terminal paths are too easy to misread as “completed work”

What it claims:
- Current contract material allows an ODR-only run to be MAR complete and replay ready.

What it does:
- A prebuild-only path with zero turn capture can still satisfy those technical completeness surfaces.

Why this is behaviorally dangerous:
- The technical claim may be true, but the product interpretation is easy to misread.
- Operators will assume completion means “artifact-producing execution happened.”

Required correction:
- Split lifecycle meaning from evidence completeness.
- Introduce separate human-facing outcome classes.

### 8. Determinism evidence has historically overstated what was proven

What it claims:
- Some benchmark/test surfaces imply determinism proof.

What it does:
- Archived reviews explicitly call out fixture-to-itself and single-run determinism truth debt.

Why this is behaviorally wrong:
- One run or identical-fixture comparison does not prove runtime determinism.
- The green signal looks stronger than the underlying evidence.

Required correction:
- Reserve determinism language for multi-run real-artifact proof.
- Rename weaker checks as smoke, comparator identity, or shape consistency.

### 9. Child-schema duality (`cards` vs `issues`) is still a behavior trap

What it claims:
- Epic child items are conceptually one thing.

What it does:
- Archived current-state implementation planning still treats mixed `cards` / `issues` handling as an active seam in touched paths.

Why this is behaviorally wrong:
- Same concept, two authorities.
- Operators and UI consumers will create the wrong thing through whichever spelling survives first.

Required correction:
- One canonical child key: `issues`.
- Boundary normalization only for legacy compatibility.

## Product Consequence

Without fixing these seams, the UI would lie in at least five ways:

1. it would show buttons for non-real actions,
2. it would imply clean-run isolation where session carryover may survive,
3. it would show ODR as independent critique when it may be self-audit,
4. it would treat missing runtime facts as absence rather than failure, and
5. it would show “complete” for runs that never produced the kind of result operators think they are looking at.

## Bottom Line

The current behavioral risk is no longer broad chaos. It is concentrated mislabeling at exactly the surfaces that matter most for productization.

That is fixable.

But the rule should be strict:

**Any label, badge, button, or success state in the UI must correspond to a real enforced runtime fact, not a convenient interpretation.**
