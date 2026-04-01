# Runtime OS Implementation Plan
Last updated: 2026-04-01
Status: Completed (archived requirements-hardening meta-lane)
Owner: Orket Core
Lane type: Runtime OS future-lane selection / archived requirements-hardening meta-lane

Archived requirements companion: `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`
Closeout authority: `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/CLOSEOUT.md`
Promoted follow-on lane (now completed): `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`

## Authority posture

This document is the archived lane record for the completed RuntimeOS requirements-hardening meta-lane.

The paired archived requirements companion is `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`.
The promoted follow-on lane now lives at `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`.

This archived record preserves the hardening logic used to close the meta-lane.
It no longer acts as the active roadmap authority.

## Source authorities

This lane is bounded by:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`
2. `docs/ROADMAP.md`
3. `docs/ARCHITECTURE.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
6. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`
7. `docs/projects/future/brainstorm/orket_brainstorm_runtime_os_extensions_2026-03-31_v5.md`

## Purpose

Turn the Runtime OS future-lane staging packet into live requirements authority and choose the strongest bounded next lane without pretending that all six grouped items should activate at once.

This lane exists to answer:
1. which grouped items are ready for promotion
2. which grouped items still need splitting
3. which grouped items must remain deferred
4. what the first real downstream lane should be

## Non-goals

This lane does not:
1. activate six separate roadmap entries at once
2. claim implementation truth for any grouped item before acceptance
3. reopen Graphs by implication
4. write `docs/specs/` contracts before a grouped item is accepted tightly enough to justify them
5. turn one meta-lane into a broad runtime-OS rewrite

## Decision lock

The following remain fixed while this lane is active:
1. the lane stays requirements-first
2. grouped items may be promoted, deferred, split, or rejected independently
3. the roadmap points only to this canonical meta-lane path, not to the earlier `future/` packet
4. no grouped item becomes a separate roadmap entry until it has explicit scope, non-goals, proof expectations, and same-change update targets
5. Item 4 may split later if package-surface hardening and publish-surface hardening prove to be different lane shapes
6. Item 6 remains conditional and blocked on explicit roadmap reopen authority plus durable underlying lineage

## Active grouped workstreams

### Workstream 1 - Governed turn-tool approval continuation

Objective:
1. decide whether governed turn-tool approval continuation can become one real bounded runtime contract

Current narrowing target:
1. the current first candidate is one issue-scoped `tool_approval` pending-gate slice on the default governed turn-tool path rather than a broad family of approval-required tools
2. that candidate is still rooted in the archived governed turn-tool destructive-mutation path on `issue:<issue_id>`, but it must narrow to one policy-declared tool name or one exact mutation subtype before promotion
3. the default first narrowing candidate is `write_file` because current request-creation and operator-action proofs already exercise that path truthfully
4. built-in seat policy still returns no approval-required tools by default, so this workstream must not pretend a broad live approval family already exists
5. current runtime truth for the candidate remains limited to approval request creation, operator-visible inspection or decision surfaces, and terminal stop outcomes
6. no approve-to-continue execution contract currently exists for that candidate
7. if this candidate cannot stay bounded without reopening broader checkpoint, resume, or multi-capability platform scope, Workstream 2 becomes the first-promotion candidate instead of widening Workstream 1

Required outputs:
1. one selected tool name or exact mutation subtype
2. one explicit continuation lifecycle
3. one fail-closed precondition story
4. one real-path proof expectation

Promotion bar:
1. one selected issue-scoped turn-tool tool-approval slice must remain admitted
2. the promoted slice must name its request shape explicitly, including the `tool_approval` request family and `approval_required_tool:<tool_name>` reason form when that form remains selected
3. one real-path proof must exist for request, inspect, approve-or-deny, and explicit continuation-or-stop behavior on that selected slice
4. one fail-closed proof must exist for missing or drifted approval, target-run identity, or namespace authority on that selected slice
5. the promoted slice must not silently widen from one selected tool or subtype into every tool listed by `approval_required_tools`
6. same-change promotion must name the exact operator-facing and authority-update surfaces affected by the selected slice

Current proof baseline:
1. request creation is currently covered on the `write_file` candidate by `tests/application/test_orchestrator_epic.py`, including `tool_approval`, `approval_required_tool:write_file`, and the turn-tool `control_plane_target_ref`
2. stop-before-execution behavior is currently covered on the `write_file` candidate by `tests/application/test_turn_executor_middleware.py` and `tests/application/test_turn_tool_dispatcher.py`
3. approval inspection and resolution projection on the request-and-stop seam are currently covered by `tests/application/test_engine_approvals.py`, `tests/application/test_tool_approval_control_plane_reservation_service.py`, `tests/application/test_tool_approval_control_plane_operator_service.py`, `tests/interfaces/test_api_approvals.py`, and `tests/interfaces/test_api_approval_projection_fail_closed.py`
4. the missing proof is still the reason this remains a requirements lane: no real-path approve-to-continue governed turn-tool execution proof exists for the selected slice

Current change-surface baseline:
1. policy declaration and turn-context assembly currently live on `orket/decision_nodes/builtins.py` and `orket/application/workflows/orchestrator_ops.py`
2. request-and-stop preflight and tool-execution blocking currently live on `orket/application/workflows/turn_tool_dispatcher.py` and `orket/application/workflows/turn_tool_dispatcher_protocol.py`
3. approval-hold reservation and operator-action publication currently live on `orket/application/services/tool_approval_control_plane_reservation_service.py` and `orket/application/services/tool_approval_control_plane_operator_service.py`
4. approval read and decision projection currently live on `orket/orchestration/engine_approvals.py` and `orket/interfaces/routers/approvals.py`
5. any later Section A promotion must name which subset of those seams changes, rather than treating the whole family as implied scope

Current hardening decisions recorded in this lane state:
1. the admitted first-promotion candidate remains one opt-in `write_file` slice only, with request shape `tool_approval` plus `approval_required_tool:write_file`
2. the selected governed target remains the already-created turn-tool run referenced by `control_plane_target_ref` on the default `issue:<issue_id>` namespace path
3. current approved resolution truth on this slice remains limited to approval-row resolution, approval-hold release, and approval plus target-run risk-acceptance projection when durable target truth exists; it is not yet governed turn-tool execution continuation
4. current denied resolution truth already remains terminal stop on the selected request-and-stop seam
5. the only admitted first-promotion continuation shape is one runtime-owned continue step on that same selected target run after approval
6. if Workstream 1 needs a new operator-visible resume API, replacement-attempt semantics, post-effect reconciliation scope, or a wider approval-required tool family, it is no longer the first-promotion candidate and Workstream 2 takes precedence
7. any later Section A promotion must update the exact subset of the change-surface baseline above plus `CURRENT_AUTHORITY.md`, `docs/API_FRONTEND_CONTRACT.md`, and `docs/RUNBOOK.md`

### Workstream 2 - Sessions plus context-provider pipeline

Objective:
1. decide the cleanest bounded continuity lane that keeps `session_id` host-owned and provider inputs explicit

Required outputs:
1. one canonical session model
2. one explicit provider-input boundary
3. one operator-visible session inspection and cleanup boundary
4. one replay and reconstruction boundary

### Workstream 3 - Runtime seam extraction and facade reduction

Objective:
1. decide whether one bounded seam-extraction lane can reduce hot-path blast radius without pretending to finish full architecture convergence

Risk note:
1. this is currently the highest narrowing-risk grouped family because it can drift into architecture-cleanup language unless it picks one exact seam family and one behavior-parity proof set

Required outputs:
1. one selected seam family
2. one explicit composition target
3. one delegation-reduction target if applicable
4. one behavior-parity proof set

### Workstream 4 - Extension package / validate / publish hardening

Objective:
1. decide whether extension package hardening still holds as one lane shape or must split before promotion

Required outputs:
1. one canonical package or install path
2. one explicit validation and capability declaration surface
3. one operator-facing path
4. explicit split or no-split decision for package versus publish hardening

### Workstream 5 - Canonical surface cold-down and identity alignment

Objective:
1. identify one bounded wrapper and identity-alignment lane that reduces drift without turning into broad repo messaging work

Required outputs:
1. selected wrapper retirement targets
2. selected identity surfaces to align
3. migration and proof discipline for the selected cold-down slice

### Workstream 6 - Conditional Graphs reopen

Objective:
1. keep the Graphs candidate honest and deferred until explicit reopen conditions are satisfied

Required outputs:
1. explicit blocked posture
2. authority-graph and decision-graph narrow-family lock
3. explicit statement that no execution implication exists before reopen

## Recommended sequencing

The current recommended order remains:
1. governed turn-tool approval continuation
2. sessions plus context-provider pipeline
3. extension package / validate / publish hardening
4. runtime seam extraction and facade reduction
5. canonical surface cold-down and identity alignment
6. conditional Graphs reopen for authority and decision views only

This sequence may be revised only if the requirements companion changes in the same change.
The most likely future sequencing revision is a swap between Workstreams 3 and 4 if extension hardening proves to depend on colder runtime seams first.

## Final workstream dispositions

At closeout:
1. Workstream 1 was deferred. The selected issue-scoped `write_file` approval slice stayed bounded, but it still lacked the required real-path approve-to-continue proof and would have widened if promoted early.
2. Workstream 2 was promoted as the first bounded follow-on lane through `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`.
3. Workstream 3 was deferred because it still lacked one exact seam family and one behavior-parity proof set.
4. Workstream 4 was split into package-surface hardening and publish-surface hardening, with neither split child lane activated in this change.
5. Workstream 5 was deferred behind the promoted session continuity lane.
6. Workstream 6 was deferred and remained blocked on explicit roadmap reopen authority plus durable lineage.

## Outcome

This meta-lane closed successfully because:
1. all six grouped items reached a truthful final disposition of promote, defer, or split
2. the first promoted follow-on lane is now explicit and bounded
3. the roadmap now points to that promoted lane without ambiguity
4. the staging packet, archived meta-lane record, and completed follow-on lane archive now tell one authority story

## First-promotion readiness gate

The first downstream lane is ready only when:
1. one grouped item has explicit scope and non-goals in the requirements companion
2. one truthful proof set is named for that grouped item
3. required source-of-truth update targets are named
4. the grouped item no longer depends on unresolved broad scope arguments
5. the future packet can remain historical staging input rather than live authority

## Lane completion gate

This lane was complete only when:
1. at least one grouped item is ready for clean promotion into its own bounded lane
2. all six grouped items have a truthful status of promote, defer, split, or reject
3. the roadmap can be rewritten from this meta-lane to the selected promoted lane or lanes without ambiguity
4. the `future/` staging packet, this plan, and the requirements companion tell one authority story

## Stop conditions

Stop and narrow scope conditions while this lane was active:
1. this lane starts acting like six active lanes at once
2. one grouped item grows broad enough to hide a second lane inside it
3. Graphs begin to look active without explicit reopen authority
4. package and publish hardening drift apart but the lane keeps pretending they are one clean shape
5. roadmap wording starts implying code implementation where this lane has only hardened requirements
