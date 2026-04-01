# Runtime OS Requirements
Last updated: 2026-04-01
Status: Completed (archived requirements companion)
Owner: Orket Core
Lane type: Runtime OS future-lane selection / archived requirements hardening

Archived implementation authority: `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_IMPLEMENTATION_PLAN.md`
Closeout authority: `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/CLOSEOUT.md`
Promoted follow-on lane (now completed): `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`

## Authority posture

This document is the archived scoped requirements companion for the completed RuntimeOS requirements-hardening meta-lane.
It is not the active implementation authority.

The archived implementation authority for this meta-lane is `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_IMPLEMENTATION_PLAN.md`.
The promoted follow-on lane now lives at `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`.
The earlier staging packet under `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md` remains historical staging input only and does not compete with the promoted lane.

## Purpose

Turn the six-item Runtime OS staging packet into live requirements authority that can later promote one or more bounded lanes without reopening broad scope questions.

This archived requirements companion records how the repo moved from one future-facing six-item staging packet to one selected promoted follow-on lane without activating all six grouped items at once.

## Source authorities

This lane is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
5. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`
6. `docs/projects/future/brainstorm/orket_brainstorm_runtime_os_extensions_2026-03-31_v5.md`

The `future/` packet and brainstorm memo remain source inputs only.
This file is the live requirements authority for the open lane.

## Cross-lane invariants

### RO-01. No stealth roadmap expansion
The six grouped candidates may be hardened here, but they must not silently become six active roadmap entries by implication.

### RO-02. No second runtime authority
Any promoted lane must preserve host-owned runtime authority.
Clients, operators, schedulers, extensions, and graph views may project, request, or inspect, but they must not become hidden truth centers.

### RO-03. No requirements-to-implementation leap by implication
Hardening a grouped candidate into live requirements authority does not automatically authorize runtime implementation.
If a promoted candidate later contains durable contracts, those contracts must be extracted truthfully before downstream implementation planning.

### RO-04. No Graphs reopen by implication
Graphs remain deferred unless they are explicitly reopened by roadmap authority after the needed runtime lineage is already durable and truthful.

### RO-05. No broad runtime-OS rewrite under one lane
Each promoted grouped item must remain bounded enough to become one real lane with explicit non-goals and proof expectations.

## Requirements

## Section A - Governed turn-tool approval continuation

Current narrowing baseline:
1. unless the same change truthfully selects a narrower admitted subtype, Section A targets one issue-scoped governed turn-tool `tool_approval` slice rooted in the archived destructive-mutation candidate on the default `issue:<issue_id>` namespace path
2. the default first narrowing candidate is `write_file` because current request-creation and operator-action proofs already exercise that path truthfully
3. built-in seat policy still returns no approval-required tools by default, so Section A must not pretend a broad live approval-required tool family already exists
4. current runtime truth for that candidate is request creation plus operator-visible inspection or decision surfaces and terminal stop outcomes only
5. Section A is not promotion-ready until it defines an explicit continuation contract rather than re-describing the existing request-and-stop seam

Section A hardening lock for the current lane state:
1. the selected admitted capability class for first-promotion hardening is one opt-in `write_file` turn-tool slice only; no second tool name or broader mutation family is admitted in this lane state
2. the selected request shape remains `request_type=tool_approval` with `reason=approval_required_tool:write_file`
3. the selected governed target remains the already-created issue-scoped turn-tool run named by `control_plane_target_ref`, with the current target shape `turn-tool-run:<session_id>:<issue_id>:<seat_name>:<turn_index>`
4. the selected namespace rule remains the default `issue:<issue_id>` path already enforced on the governed turn-tool flow
5. current shipped approval resolution on this slice is limited to approval-row resolution, approval-hold reservation release or invalidation, and operator-action publication on the approval request plus the target run when durable target truth exists
6. an approved resolution on this slice is not yet execution continuation; it is resolved approval evidence only until a later promoted lane proves a runtime-owned continue path
7. denial already remains the truthful terminal outcome on the current request-and-stop seam
8. built-in seat policy default still returns no `approval_required_tools`; any proof for this slice must opt in exactly `write_file` and must fail closed if policy widens without same-change authority updates

### RR-01. One approval-required turn-tool slice
The lane must define exactly one governed turn-tool approval-required tool slice suitable for future promotion.

That slice must name:
1. what exact tool name or exact mutation subtype is gated
2. what run target is continued or terminated
3. what authority records own truth for the selected path
4. what operator action surface resolves the gate
5. what issue-scoped namespace rule remains fixed for the selected path
6. what request family and reason form identify the selected path when the current `tool_approval` / `approval_required_tool:<tool_name>` shape remains selected

### RR-02. Explicit continuation lifecycle
The lane must define one explicit lifecycle for:
1. pending hold creation
2. inspection
3. approve or deny resolution
4. continuation or terminal stop

The lifecycle must not stop at request creation only.

Current lifecycle boundary admitted by this lane state:
1. the real path today is request creation -> inspection -> approve-or-deny resolution -> approval-hold release or invalidation plus operator-action publication
2. approval on this slice currently resolves only the approval gate records; it does not yet cause governed turn-tool execution to continue
3. the first promoted Section A lane is admitted only if it adds exactly one runtime-owned continuation step on the already-selected target run after approval
4. that first continuation step must not widen into a new run target, a second tool family, or a general approval platform

### RR-03. Fail-closed continuation preconditions
The selected turn-tool slice must name the missing or drifted preconditions that block continuation.

At minimum it must name:
1. approval authority
2. target-run identity alignment
3. checkpoint or recovery prerequisites if any are admitted
4. target resource or namespace authority
5. what existing request-and-stop behavior remains the truthful fallback until those preconditions are satisfied

Current precondition lock for first-promotion hardening:
1. approval decision authority must resolve the latest still-pending `tool_approval` request for the selected `write_file` slice only
2. payload `control_plane_target_ref`, approval-hold reservation holder, and the governed turn-tool run chosen for continuation must agree on one run identity
3. the governed run must still own the default `issue:<issue_id>` namespace authority required by its latest durable target resource and reservation or lease story
4. the first promotion may depend only on already-durable pre-effect governed turn-tool checkpoint lineage; if it needs a new operator-visible resume API, replacement-attempt semantics, or post-effect reconciliation scope, Section A is too broad and Workstream 2 becomes the first-promotion candidate
5. until those conditions are met and live proof exists, the truthful fallback remains the current request-and-stop seam even when approval resolution publishes released-hold or risk-acceptance evidence

### RR-04. Proof expectation
The selected turn-tool slice is not ready for promotion unless one real-path proof path can exist for the admitted capability class.

That proof expectation must include:
1. one real-path request -> inspect -> approve-or-deny -> explicit continuation-or-stop proof for the selected issue-scoped turn-tool slice
2. one fail-closed proof for missing or drifted approval, target-run identity, or namespace authority on that slice
3. one truthful same-change update set for operator-facing approval and authority surfaces touched by that promoted slice
4. proof that the promoted slice remains one named tool or subtype rather than a silent widening of all `approval_required_tools`

Current proof baseline for Section A:
1. request creation on the current `write_file` candidate is already covered by `tests/application/test_orchestrator_epic.py`
2. stop-before-execution behavior on that candidate is already covered by `tests/application/test_turn_executor_middleware.py` and `tests/application/test_turn_tool_dispatcher.py`
3. approval inspection and resolution projection on the request-and-stop seam are already covered by `tests/application/test_engine_approvals.py`, `tests/application/test_tool_approval_control_plane_reservation_service.py`, `tests/application/test_tool_approval_control_plane_operator_service.py`, `tests/interfaces/test_api_approvals.py`, and `tests/interfaces/test_api_approval_projection_fail_closed.py`
4. Section A remains unpromotable until the proof set adds one real-path continuation proof after approval for the selected turn-tool slice

Current same-change update target lock for a later Section A promotion:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/API_FRONTEND_CONTRACT.md`
6. `docs/RUNBOOK.md`
7. one extracted contract path if Section A becomes durable enough to justify a standalone spec before downstream implementation planning

## Section B - Sessions plus context-provider pipeline

### RR-05. Canonical session identity
The lane must define one canonical host-owned session model distinct from invocation identity.

### RR-06. Scope separation
The lane must define explicit separation between:
1. session memory
2. profile memory
3. workspace memory

### RR-07. Context-provider boundary
The lane must define one bounded context-provider injection model that names the admitted provider inputs and reconstruction boundary for the selected session slice.

### RR-08. Operator-visible session surfaces
The lane must define the minimum operator-visible session summary, lineage, replay, and cleanup boundaries needed for truthful continuity.

## Section C - Runtime seam extraction and facade reduction

This is currently the most abstract grouped family in the lane.
It is not promotion-ready unless it narrows to one exact seam family with explicit behavioral-parity proof.

### RR-09. Selected seam family only
The lane must identify one bounded hot-path seam family for extraction or facade reduction rather than treating repo-wide modularization as the deliverable.

### RR-10. Explicit composition
The lane must define how the selected seam family becomes more explicit in composition and responsibility boundaries.

### RR-11. Delegation reduction
If `__getattr__` or equivalent magic delegation is in scope, the lane must state exactly how that delegation will be reduced or removed.

### RR-12. Behavioral parity proof
The lane must name parity proof expectations so seam cleanup does not become false-green structural cleanup only.

## Section D - Extension package / validate / publish hardening

### RR-13. One canonical package surface
The lane must define one canonical extension package or install surface that remains subordinate to host-owned runtime authority.

### RR-14. Validation and capability declarations
The lane must define explicit manifest validation, permission or capability declarations, and compatibility expectations for the selected extension surface.

### RR-15. Operator and author path
The lane must define one operator-facing path and one extension-author path that do not require repo-internal knowledge.

### RR-16. Split-if-needed rule
This grouped item may later split if package-surface hardening and publish-surface hardening prove to be different lane shapes.
The live requirements lane must decide that split explicitly before roadmap promotion if the shape no longer holds cleanly.

## Section E - Canonical surface cold-down and identity alignment

### RR-17. Wrapper retirement target
The lane must identify the specific wrapper or compatibility surfaces that are candidates for retirement, narrowing, or demotion.

### RR-18. One outward identity story
The lane must identify the selected high-signal docs and surfaces that must converge on one outward identity and supported-surface story.

### RR-19. Migration discipline
The lane must define migration or compatibility rules so surface cold-down does not create silent breakage or unsupported overclaim.

## Section F - Conditional Graphs reopen for authority and decision views only

### RR-20. Explicit reopen prerequisite
Graphs must not be promoted from this grouped item without explicit roadmap reopen authority.

### RR-21. Narrow family lock
If Graphs are ever promoted from this grouped item, they must stay limited to:
1. authority graph
2. decision graph

### RR-22. Existing lineage only
The selected graph views must read from already-authoritative runtime lineage.
This grouped item must not invent new lineage to make graph views possible.

## Recommended candidate order

The current strongest order remains:
1. governed turn-tool approval continuation
2. sessions plus context-provider pipeline
3. extension package / validate / publish hardening
4. runtime seam extraction and facade reduction
5. canonical surface cold-down and identity alignment
6. conditional Graphs reopen for authority and decision views only

This order is a lane-selection recommendation, not a command to activate all six items.
Items 3 and 4 may swap later if the requirements hardening shows that truthful extension-surface promotion depends on colder runtime seams first.

## Final grouped-item disposition

At closeout:
1. Section A was deferred. It remained bounded to one opt-in `write_file` slice, but it still lacked one truthful continuation proof and could not be promoted on request-and-stop evidence.
2. Section B was promoted through `docs/projects/archive/RuntimeOS/RTOS04012026-SESSION-CONTINUITY-CLOSEOUT/SESSION_CONTINUITY_IMPLEMENTATION_PLAN.md`.
3. Section C was deferred because it still lacked one exact seam family and one behavior-parity proof set.
4. Section D was split into package-surface hardening and publish-surface hardening before any future reopen.
5. Section E was deferred behind the promoted continuity lane.
6. Section F was deferred and remained blocked on explicit roadmap reopen authority plus durable lineage.

## Promotion outcome

This archived requirements companion closed successfully because:
1. one bounded first-promotion candidate was identified
2. truthful proof expectations and source-of-truth update targets had already been written for the selected candidate families
3. the session-continuity follow-on lane was selected without over-claiming the blocked turn-tool continuation slice
4. the roadmap can now point to one canonical non-brainstorm path without ambiguity

## Current same-change update baseline

If Section A is promoted, the same change must at minimum update:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/API_FRONTEND_CONTRACT.md`
6. `docs/RUNBOOK.md`
7. the operator-facing authority surfaces affected by the selected approval slice
8. one canonical promoted-lane path and any extracted contract path required for truthful downstream implementation planning

Current Section A change-surface baseline:
1. `orket/decision_nodes/builtins.py`
2. `orket/application/workflows/orchestrator_ops.py`
3. `orket/application/workflows/turn_tool_dispatcher.py`
4. `orket/application/workflows/turn_tool_dispatcher_protocol.py`
5. `orket/application/services/tool_approval_control_plane_reservation_service.py`
6. `orket/application/services/tool_approval_control_plane_operator_service.py`
7. `orket/orchestration/engine_approvals.py`
8. `orket/interfaces/routers/approvals.py`

Section A promotion must select a subset of that baseline explicitly.
It must not treat the entire family above as automatic scope.

If Section B is promoted, the same change must at minimum update:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-LANE-CLOSEOUT/RUNTIME_OS_REQUIREMENTS.md`
4. `CURRENT_AUTHORITY.md`
5. the session-facing authority surfaces affected by the selected continuity slice
6. one canonical promoted-lane path and any extracted contract path required for truthful downstream implementation planning

## Requirements completion gate

This live requirements lane is complete only when:
1. each grouped item is either:
   1. ready for promotion,
   2. explicitly deferred, or
   3. explicitly split or rejected
2. one bounded first-promotion candidate is identified
3. proof expectations are written truthfully for that candidate
4. same-change source-of-truth update targets are named for that candidate
5. the roadmap can later point to one canonical non-brainstorm path without ambiguity
