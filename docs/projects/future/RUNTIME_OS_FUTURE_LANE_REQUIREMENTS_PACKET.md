# Runtime OS Future Lane Requirements Packet

Last updated: 2026-04-01
Status: Superseded staging ancestor for archived RuntimeOS lanes
Owner: Orket Core
Source brainstorm: `docs/projects/future/brainstorm/orket_brainstorm_runtime_os_extensions_2026-03-31_v5.md`
Archived RuntimeOS lane records:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`
4. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This file is not roadmap authority.
It is not an active implementation plan.
It does not reopen any lane by itself.

It now survives as the staging ancestor that fed the archived RuntimeOS meta-lane and the completed session-continuity follow-on lane.
It should not compete with those archived lane records.
The split child `Extension Publish Surface Hardening` has now been promoted into active roadmap authority at `docs/projects/Extensions/EXTENSION_PUBLISH_SURFACE_HARDENING_IMPLEMENTATION_PLAN.md`.
This packet remains historical split context plus deferred-candidate staging for everything else.

Roadmap hold rule for this file:
1. do not copy these items into `docs/ROADMAP.md` yet
2. do not treat this packet as accepted requirements yet
3. do not imply an active lane until one or more items below are explicitly accepted and promoted

## Source authorities

This packet is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
5. `docs/projects/future/brainstorm/orket_brainstorm_runtime_os_extensions_2026-03-31_v5.md`

The brainstorm memo remains non-authority strategy input.
This packet narrows it into a future selection surface only.

## Purpose

Define six grouped future-lane requirements candidates that fit the current repo posture:
1. one extension publish split child is now active outside this packet
2. SupervisorRuntime Packet 1 is closed
3. the next good move should be a small number of bounded lanes rather than a broad roadmap explosion

## Selection rules

The grouped items below must remain:
1. bounded enough to become real requirements lanes later
2. small enough to evaluate independently
3. explicit about non-goals so they do not silently widen into a generic runtime-OS rewrite
4. ordered so the earlier items make later items easier to verify

## Item 1 - Governed turn-tool approval continuation

### Purpose

Finish the still-open approval gap left after SupervisorRuntime Packet 1.

The archived closeout already records the truth:
1. governed turn-tool approval-required tool requests exist
2. those requests are currently request-and-stop seams only
3. the shipped approve-to-continue Packet 1 slice was narrowed to governed kernel `NEEDS_APPROVAL`

This item exists to decide whether governed turn-tool approval continuation should become a real runtime contract.

### In scope

1. one governed turn-tool approval-required capability class
2. one explicit approve-or-deny continuation lifecycle for that class
3. one truthful target-run continuation rule
4. one operator-visible lineage story from pending hold through continuation or terminal stop
5. one real-path proof path for the selected turn-tool slice

### Out of scope

1. universal safe-tooling coverage
2. broad checkpoint and resume platform work
3. multiple approval-required capability classes
4. a general approval platform beyond the selected turn-tool slice

### Acceptance boundary

1. the selected turn-tool path no longer stops at request creation only
2. approval and denial both map to explicit runtime-owned outcomes
3. continuation does not rely on hidden implied authority
4. one live proof exists for the selected governed turn-tool slice

## Item 2 - Sessions plus context-provider pipeline

### Purpose

Turn continuity into a colder runtime primitive instead of glue spread across interaction and orchestration seams.

### In scope

1. one canonical session identity model
2. explicit session memory vs profile memory vs workspace memory boundaries
3. one bounded context-provider injection model
4. session lineage, summary, and cleanup rules for the admitted slice
5. replay and reconstruction boundaries for session-facing inspection

### Out of scope

1. broad Companion or frontend product UX
2. large knowledge-ranking or memory-search ambitions
3. broad retention-product design
4. turning client repos into continuity authority seams

### Acceptance boundary

1. one canonical session model exists
2. provider inputs are explicit and bounded
3. session summary and replay boundaries are operator-visible
4. host-owned continuity stays explicit

## Item 3 - Runtime seam extraction and facade reduction

### Purpose

Reduce change blast radius across the hottest orchestration seams without claiming a full architecture convergence finish.

### In scope

1. explicit execution-surface composition on the `turn_executor` seam
2. reduction of magic delegation and facade ambiguity
3. bounded extraction or decomposition work on the largest hot-path orchestration files
4. clearer responsibility splits across runtime entrypoint, orchestration, and interface seams

### Out of scope

1. repo-wide modularization as an end in itself
2. large directory renames with weak proof value
3. architecture-cleanup claims broader than the touched seam family
4. unrelated behavioral redesign

### Acceptance boundary

1. touched hot-path seams have smaller public shapes
2. `__getattr__`-style delegation on the selected core seam is removed or reduced explicitly
3. proof coverage shows behavior parity for the touched seam family
4. no new authority drift is introduced while extracting seams

## Item 4 - Extension package surface hardening

### Purpose

Promote extensions from mostly runtime-internal capability surfaces into one explicit operator-facing package contract without creating a second runtime authority center.
The combined package-plus-publish candidate is retired.
Future extension reopen work must choose package-surface hardening or publish-surface hardening separately instead of reviving the old combined shape.
The package-surface child of that split is complete and archived at `docs/projects/archive/Extensions/EX04012026-PACKAGE-SURFACE-HARDENING-CLOSEOUT/`.

### In scope

1. one canonical install and validate story
2. manifest validation and explicit permission or capability declarations
3. versioning and compatibility rules
4. operator-facing inspect and audit expectations
5. extension-author documentation that does not require repo-internal knowledge

### Out of scope

1. public marketplace
2. cloud-hosting platform work
3. monetization or distribution strategy
4. public release, registry, or discovery-flow expansion
5. multiple competing package surfaces in parallel

### Acceptance boundary

1. extension install and validate have one canonical operator path
2. capability and permission declarations are explicit
3. extension failure modes are governed and inspectable
4. host-owned runtime authority remains explicit

## Item 5 - Canonical surface cold-down and identity alignment

### Purpose

Reduce wrapper debt and outward identity drift so repo posture, supported surfaces, and operator expectations stop competing with one another.

### In scope

1. retirement or narrowing of compatibility wrappers where the canonical path is already known
2. explicit cold-down of outward runtime surfaces
3. repo identity alignment across top-level descriptive surfaces
4. bounded supported-surface wording cleanup

### Out of scope

1. marketing rewrite work
2. broad product-positioning exploration detached from runtime truth
3. compatibility removal without migration or proof
4. deep package refactors that belong in Item 3 instead

### Acceptance boundary

1. one outward identity story is present across the selected high-signal docs
2. wrapper surfaces are retired, narrowed, or explicitly demoted
3. the canonical public runtime surface is clearer than before
4. documentation and code no longer imply competing supported-surface stories

## Item 6 - Conditional Graphs reopen for authority and decision views only

### Purpose

Define the narrowest future Graphs reopen worth considering after the runtime seams above are colder.

### Preconditions

1. Graphs must be explicitly reopened by roadmap authority before any execution work is implied
2. the underlying runtime lineage needed by the selected graph views must already be durable and truthful

### In scope after explicit reopen

1. authority graph
2. decision graph
3. filtered-view framing over existing durable truth surfaces
4. one operator reason for why each admitted graph view exists

### Out of scope

1. workload-composition graphing
2. counterfactual or comparison graphing
3. lineage invention unsupported by existing records
4. broad graph-family expansion

### Acceptance boundary after explicit reopen

1. the reopen is explicit in roadmap authority
2. one canonical operator path exists per admitted graph view
3. one proof path exists per admitted graph view
4. both views read from existing durable truth rather than ad hoc scraping

## Recommended sequence

The strongest split sequence is:
1. governed turn-tool approval continuation
2. sessions plus context-provider pipeline
3. extension package surface hardening
4. extension publish surface hardening
5. runtime seam extraction and facade reduction
6. canonical surface cold-down and identity alignment
7. conditional Graphs reopen for authority and decision views only

Why this order:
1. it closes the most concrete remaining runtime-truth gap first
2. it hardens continuity before broader surface expansion
3. it lets package-surface hardening land before any publish or distribution reopen
4. it keeps extension work subordinate to host-owned authority
5. it delays graph-family work until the runtime seams beneath it are colder

## Draft Priority Now block

Hold only.
Do not copy this into `docs/ROADMAP.md` until requirements are accepted.

1. governed turn-tool approval continuation -- Requirements candidate for one approval-required turn-tool lifecycle with explicit approve-or-deny continuation and real-path proof.
2. sessions plus context-provider pipeline -- Requirements candidate for one canonical session model, provider injection boundary, and host-owned continuity story.
3. extension publish surface hardening -- Promoted out of this packet into active roadmap authority at `docs/projects/Extensions/EXTENSION_PUBLISH_SURFACE_HARDENING_IMPLEMENTATION_PLAN.md`; do not duplicate it from this packet.
4. runtime seam extraction and facade reduction -- Requirements candidate for bounded hot-path seam extraction, explicit composition, and delegation reduction.
5. canonical surface cold-down and identity alignment -- Requirements candidate for wrapper retirement, outward identity alignment, and clearer canonical runtime surfaces.
6. conditional Graphs reopen for authority and decision views only -- Deferred requirements candidate that stays blocked until explicitly reopened after underlying runtime seams are colder.

## Requirements completion gate

Do not move any of the six items above into the roadmap until:
1. the selected item or items have explicit scope and non-goals written as requirements authority
2. proof expectations are named truthfully
3. same-change source-of-truth update targets are named
4. the selected item can become one bounded lane without reopening basic scope questions
5. the roadmap entry can point to one canonical non-brainstorm path
