# Runtime Convergence and Simplification Requirements

Last updated: 2026-04-02
Status: Draft staged future-lane requirements
Authority status: Staging only. Not current roadmap authority. Not current execution authority until explicitly adopted.
Owner: Orket Core
Lane family: Internal runtime hardening

## Purpose

Reduce internal runtime drift, wrapper debt, and hot-path seam complexity by driving one bounded convergence and simplification packet at a time.

This lane exists to improve execution truth and architectural clarity without pretending that vague cleanup is a sufficient plan by itself.

## Current shipped baseline

The repo already carries a paused ControlPlane partial-convergence checkpoint and current-authority language describing that posture.
This doc does not claim that broad convergence authority is absent today.
It starts from the rule that the paused checkpoint remains the current explicit-reopen authority for that hotter lane.

## Future delta proposed by this doc

This doc proposes a bounded internal hardening packet that reduces drift without silently reopening repo-wide convergence.
Candidate deltas include:
1. workload-authority cold-down on selected start paths,
2. bounded safe-tooling default-path expansion,
3. effect-journal hardening on selected paths,
4. wrapper retirement,
5. seam extraction that reduces authority ambiguity.

## What this doc does not reopen

This doc does not reopen:
1. the paused ControlPlane convergence lane by implication,
2. a repo-wide vocabulary redesign,
3. a broad multi-lane convergence campaign hidden under refactor language,
4. graph-family work by implication.

## Usage boundary

This doc should be read as a bounded internal hardening candidate.

It should not be read as:
1. an excuse for indefinite architecture churn,
2. permission to rename or move surfaces without acceptance proof,
3. a substitute for explicitly reopening a hotter convergence lane when that is what the work really is,
4. authority to supersede the paused ControlPlane checkpoint.

## In scope

1. workload-authority cold-down,
2. safe-tooling default-path expansion where explicitly selected,
3. effect-journal default-path hardening where explicitly selected,
4. run, attempt, and step identity alignment,
5. compatibility-wrapper retirement,
6. explicit execution-surface composition,
7. bounded seam extraction from hot-path modules.

## Out of scope

1. vague architecture cleanup with no bounded packet,
2. broad vocabulary redesign,
3. product-facing feature expansion,
4. graph-family expansion by implication,
5. multi-lane convergence hidden under refactor language.

## Core requirements

### RC-01. Bounded packet only
Any adoption of this doc must name a bounded convergence packet rather than opening a repo-wide simplification campaign.

### RC-02. Cannot supersede or reopen paused ControlPlane authority by implication
This doc must remain subordinate to the paused ControlPlane checkpoint authority.
If the intended work is actually a reopen of that hotter lane, the repo must say so explicitly rather than using this doc as a surrogate.

### RC-03. Canonical workload authority first
Touched start paths must converge toward one canonical workload-authority story rather than keeping multiple equally authoritative entry vocabularies alive.

### RC-04. Compatibility wrappers are temporary and named
Any kept compatibility wrapper must:
1. name its compatibility role,
2. identify the canonical surface,
3. state an exit or projection-only condition.

### RC-05. Hot-path seam extraction must reduce authority ambiguity
Seam extraction is acceptable only when it makes execution ownership, boundary shape, or attribution clearer rather than merely redistributing code.

### RC-06. Effect truth must not drift hotter
Any selected mutation-path hardening must move toward published effect truth rather than deeper artifact reconstruction dependence.

### RC-07. Identity surfaces must align
Selected work must reduce drift across workload, run, attempt, step, and outward repo identity where those are part of the adopted packet.

### RC-08. No convenience facade as shadow authority
Facade or adapter surfaces must not become hidden alternate authority paths after the refactor.

### RC-09. Same-change doc sync required
Any accepted simplification packet must update touched authority docs, crosswalks, or boundary descriptions in the same change.

### RC-10. Transitional layers remain visibly transitional
Temporary bridges may exist, but they must remain visibly non-canonical until retired.

### RC-11. Simplification is not proof by aesthetics
Reduced file size, package movement, or prettier naming alone is not acceptance evidence.

## Acceptance boundary

This lane is acceptable only when:
1. one bounded packet is named,
2. the packet does not supersede paused ControlPlane authority by implication,
3. touched paths have clearer canonical authority,
4. kept wrappers have explicit non-authority posture and exit conditions,
5. selected seams are more explicit and less magic-driven,
6. doc and code posture remain synchronized,
7. the change reduces real execution ambiguity rather than only rearranging files.

## Proof requirements

Structural proof:
1. no new shadow authority facade exists,
2. no kept wrapper lacks an exit condition,
3. no adopted packet leaves touched authority docs knowingly stale,
4. no selected path keeps multiple co-equal canonical identities,
5. no adoption text silently reclassifies the paused checkpoint as reopened.

Integration proof:
1. representative touched paths still execute through the intended canonical surface,
2. compatibility behavior remains bounded and inspectable where retained,
3. selected run or effect attribution remains truthful after the refactor.

Live proof where real surfaces are involved:
1. operator-facing touched paths still work through the documented canonical entry,
2. transitional behavior remains visible rather than hidden,
3. no false-green conformance claim is introduced by the simplification change.

## Ordering note

This doc is fourth in the packet because it is important but hot.
It should be adopted only when the repo explicitly wants internal convergence work rather than a narrower feature lane.
