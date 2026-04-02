# Runtime OS Future Lane Requirements Packet

Last updated: 2026-04-02
Status: Historical staging ancestor for archived RuntimeOS lanes, archived extension splits, and one archived Graphs child
Owner: Orket Core
Source brainstorm: `docs/projects/future/brainstorm/orket_brainstorm_runtime_os_extensions_2026-03-31_v5.md`
Archived RuntimeOS lane records:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`
4. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/CLOSEOUT.md`
5. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_REQUIREMENTS.md`
6. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_IMPLEMENTATION_PLAN.md`
7. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/CLOSEOUT.md`
8. `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_REQUIREMENTS.md`
9. `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_IMPLEMENTATION_PLAN.md`
10. `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/CLOSEOUT.md`
11. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/TURN_EXECUTOR_SEAM_EXTRACTION_FACADE_REDUCTION_REQUIREMENTS.md`
12. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/TURN_EXECUTOR_SEAM_EXTRACTION_FACADE_REDUCTION_IMPLEMENTATION_PLAN.md`
13. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/CLOSEOUT.md`
14. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_REQUIREMENTS.md`
15. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_IMPLEMENTATION_PLAN.md`
16. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CLOSEOUT.md`
17. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_REQUIREMENTS.md`
18. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_IMPLEMENTATION_PLAN.md`
19. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This file is not roadmap authority.
It is not an active implementation plan.
It does not reopen any lane by itself.

It now survives as the staging ancestor that fed the archived RuntimeOS meta-lane and its completed follow-on children.
It should not compete with those archived lane records.
The `governed turn-tool approval continuation` child is now complete and archived at `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/`.
The split child `Extension Package Surface Hardening` is now complete and archived at `docs/projects/archive/Extensions/EX04012026-PACKAGE-SURFACE-HARDENING-CLOSEOUT/`.
The split child `Extension Publish Surface Hardening` is now complete and archived at `docs/projects/archive/Extensions/EX04012026-PUBLISH-SURFACE-HARDENING-CLOSEOUT/`.
The `sessions plus context-provider pipeline` child is now complete and archived at `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/`.
The `runtime seam extraction and facade reduction` child is now complete and archived at `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/`.
The `canonical surface cold-down and identity alignment` child is now complete and archived at `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/`.
The `conditional Graphs reopen for authority and decision views only` child is now complete and archived at `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/`.
No item in this packet is currently accepted or queued for execution.
This packet remains historical split context only, and the named staging ancestor referenced by archived closeouts when describing any future explicit RuntimeOS or Graphs reopen.

Roadmap hold rule for this file:
1. do not copy deferred items from this packet into `docs/ROADMAP.md` without explicit acceptance
2. do not treat untouched deferred items in this packet as accepted requirements yet
3. Item 1 is already complete and archived; do not duplicate it from this packet
4. Item 2 is already complete and archived; do not duplicate it from this packet
5. Item 3 is already complete and archived; do not duplicate it from this packet
6. Item 5 is already complete and archived; do not duplicate it from this packet
7. Item 6 is already complete and archived; do not duplicate it from this packet
8. Item 4's old combined extension candidate is retired; do not revive it from this packet
9. do not imply an active lane unless a newly bounded item is explicitly accepted and promoted

## Source authorities

This packet is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
5. `docs/projects/future/brainstorm/orket_brainstorm_runtime_os_extensions_2026-03-31_v5.md`

The brainstorm memo remains non-authority strategy input.
This packet narrows it into a historical future-selection surface only.

## Purpose

Preserve the historical RuntimeOS lane-candidate narrowing that fed the archived children below.
No item in this packet is currently accepted or queued for execution.
The only live authority it retains is as historical narrowing context and as the explicit named reopen source referenced by archived closeouts.

## Selection rules

The grouped items below must remain:
1. bounded enough to become real requirements lanes later
2. small enough to evaluate independently
3. explicit about non-goals so they do not silently widen into a generic runtime-OS rewrite
4. ordered so the earlier items make later items easier to verify

## Item 1 - Governed turn-tool approval continuation

This item is now complete and archived.

Archived lane authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_REQUIREMENTS.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/CLOSEOUT.md`

The staging bullets below remain historical narrowing input only.

### Purpose

Finish the remaining approval-family gap left after SupervisorRuntime Packet 1 and the shipped RuntimeOS `write_file` continuation slice.

The archived closeout already records the truth:
1. governed turn-tool approval-required tool requests exist
2. the bounded governed turn-tool `write_file` and `create_issue` slices now continue on approval and stop on denial on the same governed run
3. broader governed turn-tool approval-required families still do not have a promoted continuation contract

This item exists to decide whether any governed turn-tool approval continuation beyond the shipped `write_file` slice should become a real runtime contract.

### In scope

1. one governed turn-tool approval-required capability class beyond the already-shipped `write_file` slice
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

1. the selected additional turn-tool path no longer stops at request creation only
2. approval and denial both map to explicit runtime-owned outcomes
3. continuation does not rely on hidden implied authority
4. one live proof exists for the selected governed turn-tool slice

## Item 2 - Sessions plus context-provider pipeline

This item is now complete and archived.

Archived lane authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_REQUIREMENTS.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/SESSIONS_CONTEXT_PROVIDER_PIPELINE_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/CLOSEOUT.md`

The staging bullets below remain historical narrowing input only.

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

This item is now complete and archived.

Archived lane authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/TURN_EXECUTOR_SEAM_EXTRACTION_FACADE_REDUCTION_REQUIREMENTS.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/TURN_EXECUTOR_SEAM_EXTRACTION_FACADE_REDUCTION_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/CLOSEOUT.md`

The staging bullets below remain historical narrowing input only.

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

This combined extension-surface candidate is retired as a packet item.

Archived split-lane authority:
1. `docs/projects/archive/Extensions/EX04012026-PACKAGE-SURFACE-HARDENING-CLOSEOUT/CLOSEOUT.md`
2. `docs/projects/archive/Extensions/EX04012026-PUBLISH-SURFACE-HARDENING-CLOSEOUT/CLOSEOUT.md`

The staging bullets below remain historical narrowing input only.

### Purpose

Promote extensions from mostly runtime-internal capability surfaces into one explicit operator-facing package contract without creating a second runtime authority center.
The combined package-plus-publish candidate is retired.
Future extension reopen work must choose package-surface hardening or publish-surface hardening separately instead of reviving the old combined shape.
The package-surface child of that split is complete and archived at `docs/projects/archive/Extensions/EX04012026-PACKAGE-SURFACE-HARDENING-CLOSEOUT/`.
The publish-surface child of that split is complete and archived at `docs/projects/archive/Extensions/EX04012026-PUBLISH-SURFACE-HARDENING-CLOSEOUT/`.

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

This item is now complete and archived.

Archived lane authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_REQUIREMENTS.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CLOSEOUT.md`

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

This item is now complete and archived.

Archived lane authority:
1. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_REQUIREMENTS.md`
2. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/CLOSEOUT.md`

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

The strongest historical split sequence was:
1. governed turn-tool approval continuation (complete and archived)
2. sessions plus context-provider pipeline (complete and archived)
3. extension package surface hardening (complete and archived)
4. extension publish surface hardening (complete and archived)
5. runtime seam extraction and facade reduction (complete and archived)
6. canonical surface cold-down and identity alignment (complete and archived)
7. conditional Graphs reopen for authority and decision views only (complete and archived)

Why this order:
1. it closes the most concrete remaining runtime-truth gap first
2. it hardens continuity before broader surface expansion
3. it lets package-surface hardening land before any publish or distribution reopen
4. it keeps extension work subordinate to host-owned authority
5. it delays graph-family work until the runtime seams beneath it are colder

## Draft Priority Now block

Historical only.
Do not duplicate active or archived items from this block into `docs/ROADMAP.md`, and do not copy still-deferred items until requirements are accepted.

1. governed turn-tool approval continuation -- Complete and archived at `docs/projects/archive/RuntimeOS/RTOS04012026-CREATE-ISSUE-APPROVAL-CONTINUATION-CLOSEOUT/`; do not duplicate it from this packet.
2. sessions plus context-provider pipeline -- Complete and archived at `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/`; do not duplicate it from this packet.
3. extension package surface hardening -- Complete and archived at `docs/projects/archive/Extensions/EX04012026-PACKAGE-SURFACE-HARDENING-CLOSEOUT/`; do not duplicate it from this packet.
4. extension publish surface hardening -- Complete and archived at `docs/projects/archive/Extensions/EX04012026-PUBLISH-SURFACE-HARDENING-CLOSEOUT/`; do not duplicate it from this packet.
5. runtime seam extraction and facade reduction -- Complete and archived at `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/`; do not duplicate it from this packet.
6. canonical surface cold-down and identity alignment -- Complete and archived at `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/`; do not duplicate it from this packet.
7. conditional Graphs reopen for authority and decision views only -- Complete and archived at `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/`; do not duplicate it from this packet.

## Requirements completion gate

Do not move any still-deferred item from this packet into the roadmap until:
1. the selected item or items have explicit scope and non-goals written as requirements authority
2. proof expectations are named truthfully
3. same-change source-of-truth update targets are named
4. the selected item can become one bounded lane without reopening basic scope questions
5. the roadmap entry can point to one canonical non-brainstorm path
