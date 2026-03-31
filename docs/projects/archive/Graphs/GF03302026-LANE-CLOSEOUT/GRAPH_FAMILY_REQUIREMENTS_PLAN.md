# Graph Family Requirements Plan

Last updated: 2026-03-30
Status: Completed (archived requirements closeout authority)
Owner: Orket Core
Canonical implementation plan: `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
Lane type: Archived requirements authority / completed graph-family planning lane

Archive note:
1. Completed and archived on 2026-03-30.
2. Closeout authority: `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This document is the archived requirements authority for the completed Graphs lane.

The archived execution authority is `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`.

It does not reopen the archived Graph implementation lane at `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/`.
The shipped V1 contract remains authoritative in `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`.
Any future graph-family promotion or implementation work must reopen as a new explicit roadmap lane.

## Source authorities

This lane is bounded by:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `docs/ROADMAP.md`
3. `docs/ARCHITECTURE.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/CLOSEOUT.md`
6. the existing graph runtime surfaces already shipped for V1:
   1. `orket/runtime/run_evidence_graph.py`
   2. `orket/runtime/run_evidence_graph_projection.py`
   3. `orket/runtime/run_evidence_graph_rendering.py`
   4. `scripts/observability/emit_run_evidence_graph.py`

## Purpose

Turn the non-normative future graph-family taxonomy in Appendix A of `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` into bounded active requirements without broadening the shipped V1 contract prematurely.

This lane should answer:
1. which future graph families remain filtered views over the existing semantic core
2. which future graph families, if any, require separate artifact families
3. what operator question, bounded lineage rules, and rendering rules each promoted family must satisfy
4. which families remain explicitly deferred after requirements hardening

## In scope

Requirements hardening for:
1. authority graph
2. decision graph
3. closure graph
4. resource-authority graph
5. explicit deferral posture for workload-composition graph
6. explicit deferral posture for counterfactual or comparison graph

## Non-goals

This lane does not:
1. change the shipped V1 `run_evidence_graph` runtime or schema by default
2. implement new graph families
3. invent new runtime nouns outside already-authoritative or already-validated sources
4. reopen the archived `GR03302026-LANE-CLOSEOUT` implementation lane
5. decide UI-only graph ideas that cannot state one operator question cleanly

## Decision lock

The following remain fixed while this lane is active:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` remains the authoritative shipped V1 contract
2. Appendix A remains non-normative until a later same-change contract promotion occurs
3. future family work must remain projection-only and must not mint lineage unsupported by first-class records
4. a later family may either:
   1. reuse the current semantic graph core as a named filtered view, or
   2. land as a new artifact family only with explicit same-change contract, schema, registry, and authority updates
5. the active question is requirements hardening, not implementation

## Requirements hardening targets

The targets below define what the paired implementation plan must harden and resolve.

### Target 1 - Family-by-family operator-question hardening

Objective:
1. restate each candidate family in operator-question form and reject any family that cannot hold one clean question

Required outputs:
1. accepted operator question per in-scope family
2. rejected or deferred family list where the question is still too vague
3. explicit confirmation that the shipped V1 family remains unchanged

### Target 2 - Semantic-core reuse versus new artifact-family decision

Objective:
1. determine whether each in-scope family should remain a filtered view over the existing semantic graph JSON or requires a separate artifact family

Required outputs:
1. per-family decision: filtered view or new artifact family
2. bounded rationale for each decision
3. explicit prohibition on silent family splitting

### Target 3 - Requirement candidate hardening

Objective:
1. define bounded source rules, family-specific rendering rules, and visible-distinction requirements for each promoted family candidate

Required outputs:
1. source and lineage constraints per family
2. rendering-emphasis rules that do not replace source-family identity
3. deferred-family reopen criteria for workload-composition and counterfactual/comparison work

### Target 4 - Promotion recommendation

Objective:
1. prepare the clean handoff from requirements hardening into either:
   1. a promoted durable contract change in `docs/specs/`, or
   2. an explicit defer-or-reject decision with no implementation lane

Required outputs:
1. recommended promoted contract delta set, if any
2. explicit list of same-change surfaces that would have to move together
3. clear statement of what remains non-normative if promotion is not accepted

## Slice 1 checkpoint - operator-question freeze

Status: complete on 2026-03-30.

Accepted operator questions:
1. authority graph -> what authority chain allowed or blocked mutation and closure for this run
2. decision graph -> where routing, policy, supervisor, recovery, or reconciliation decisions changed the path for this run
3. closure graph -> what exact chain closed this run
4. resource-authority graph -> what ownership path governed reservation, lease, mutation, release, rollback, or drift for this run

Deferred at Slice 1:
1. workload-composition graph -> deferred because the current candidate question still mixes parent-child execution lineage with broader workload-composition semantics; it may reopen only when one stable operator question is restated against already-authoritative parent-child lineage
2. counterfactual or comparison graph -> deferred because the current candidate question still mixes actual truth, replay, replacement-attempt reasoning, hypothetical alternatives, and multi-run comparison; it may reopen only when one stable operator question is restated with explicit comparison basis and truth-label rules

Slice 1 locks:
1. the shipped `run_evidence_graph` family remains unchanged
2. no family is admitted past Slice 1 by rendering emphasis alone
3. Slice 2 may evaluate only `authority`, `decision`, `closure`, and `resource-authority`
4. deferred families remain outside promotion scope unless their reopen criteria are satisfied first

## Slice 2 checkpoint - semantic-core reuse decision

Status: complete on 2026-03-30.

Per-family decisions:
1. authority graph -> filtered view over the existing semantic graph core, because its operator question is answered by emphasizing already-bounded `run`, `attempt`, `reservation`, `lease`, `resource`, `operator_action`, `reconciliation`, and `final_truth` lineage rather than by minting a new lineage contract
2. decision graph -> filtered view over the existing semantic graph core, because its decision emphasis is projected from existing covered node families and validated sources, and the lane does not admit a new runtime noun or artifact family by label alone
3. closure graph -> filtered view over the existing semantic graph core, because V1 already requires a `closure_path` view and a second closure-specific artifact family would silently fork the same closure semantics
4. resource-authority graph -> filtered view over the existing semantic graph core, because V1 already requires a `resource_authority_path` view and the operator question is answered by emphasizing existing reservation, lease, resource, observation, effect, reconciliation, and final-truth lineage

Slice 2 locks:
1. no admitted Slice 2 family currently requires a separate artifact family
2. no admitted Slice 2 family may silently split schema, registry, canonical output paths, or authority posture away from the `run_evidence_graph` semantic core
3. any later claim that one of these admitted families needs a new artifact family must first show a truthful operator question that cannot be represented as a filtered view and must land only with same-change contract, schema, registry, and authority updates
4. Slice 3 may harden only `authority`, `decision`, `closure`, and `resource-authority` as filtered-view families unless deferred-family reopen criteria are satisfied first
5. the shipped `run_evidence_graph` family remains unchanged, and Appendix A remains non-normative until later promotion

## Slice 3 checkpoint - requirement candidate hardening

Status: complete on 2026-03-30.

Admitted-family requirement candidates:
1. authority graph -> source and lineage constraints: reuse the admitted semantic core and keep the authority story anchored on `run`, `attempt`, `reservation`, `lease`, `resource`, `operator_action`, `reconciliation`, and `final_truth`; include `step`, `effect`, or `observation` only when already-authoritative lineage makes them necessary to explain a mutation or closure decision; do not let an observation or effect annotation masquerade as authority and do not mint a new authority edge unsupported by first-class records
2. authority graph -> rendering-emphasis rules: emphasize reservation-to-lease promotion, lease-to-resource authority, operator-action effects on transitions or resources, reconciliation-to-final-truth closure, and final-truth-to-run closure; keep the underlying source family visible even when the view groups or suppresses non-authority nodes
3. decision graph -> source and lineage constraints: remain limited to already-covered decision-bearing families such as `checkpoint_acceptance`, `recovery_decision`, `reconciliation`, `operator_action`, and `final_truth`, plus only the supporting `attempt`, `step`, or `observation` lineage needed to show where the path changed; do not mint a generic `decision` node family and do not infer decisions from ordinary step timing or narration alone
4. decision graph -> rendering-emphasis rules: highlight path-changing decisions and their affected transition or resource refs; a future decision-focused view may specialize by attributes such as `decision_kind`, `command_class`, or `closure_basis`, but the underlying semantic family must stay visible and resource-only branches may be suppressed when they did not change the path
5. closure graph -> source and lineage constraints: stay anchored on `final_truth` and only the directly supporting `reconciliation`, `recovery_decision`, `operator_action`, `effect`, `observation`, `step`, `attempt`, and `run` lineage already tied to the closing chain; unrelated reservation or resource branches remain out unless first-class closure lineage explicitly depends on them
6. closure graph -> rendering-emphasis rules: center the closing chain on `final_truth`, its `closure_basis`, and any directly linked authoritative-result observation path; keep intermediate observations and effects visibly distinct from terminal truth and suppress non-closing branches that would blur the operator question
7. resource-authority graph -> source and lineage constraints: stay anchored on `reservation`, `lease`, and `resource`, plus directly linked `observation`, `effect`, `operator_action`, `reconciliation`, and `final_truth` lineage and only the supporting `run`, `attempt`, or `step` anchors needed to keep the authority story truthful; do not add checkpoint-heavy detail or invented mutation edges unless a later contract promotion proves those links first-class and necessary
8. resource-authority graph -> rendering-emphasis rules: emphasize reservation lifecycle, lease authority, resource current-state observation, operator actions affecting resources, and any reconciliation or final-truth outcome tied to that authority path; keep observation or effect evidence visually distinct from the authority nodes themselves

Deferred-family reopen criteria:
1. workload-composition graph may reopen only when one stable operator question is restated strictly against already-authoritative parent-child lineage, the exact parent-child or workload-link source records are named up front, and the candidate can prove it does not infer composition from prose, loose artifact co-location, or unlabeled adjacency inside the existing graph output
2. workload-composition graph may not reopen merely because a UI wants grouping; it must first show whether the existing semantic core can carry truthful parent-child linkage without inventing a second lineage contract
3. counterfactual or comparison graph may reopen only when one comparison basis is fixed up front, the candidate truth labels distinguish actual versus replayed versus replacement-attempt versus hypothetical or compared paths, and the proposal names the authoritative keys that keep those paths from collapsing into one unlabeled run story
4. counterfactual or comparison graph may not reopen merely because alternate paths look useful; it must first show whether a truthful filtered view is possible or whether a separate artifact family would be required, and that answer must be stated before any implementation lane begins

Slice 3 locks:
1. admitted future families remain filtered-view candidates over the existing semantic core and still authorize no runtime, schema, registry, or operator-path changes
2. rendering emphasis may suppress irrelevant branches, but it may not replace underlying source-family identity
3. no admitted family may introduce new node families, edge families, or canonical output paths without a later same-change promotion
4. Slice 4 may decide only promotion-ready contract deltas versus continued deferral; it may not backdoor implementation work

## Slice 4 checkpoint - promotion or defer handoff

Status: complete on 2026-03-30.

Decision:
1. no new durable contract promotion is accepted from this lane
2. recommended promoted contract-delta set: none at this time

Rationale:
1. `closure_path` and `resource_authority_path` are already normative shipped V1 view tokens, so this lane did not identify an additional durable contract delta beyond already-shipped V1 view semantics
2. `authority` and `decision` remain truthful filtered-view vocabulary over the existing semantic core, but this lane did not identify a new view token, artifact family, schema delta, or operator path that should be promoted without a later explicit implementation request
3. `workload-composition` and `counterfactual/comparison` remain explicitly deferred and do not justify promotion

Same-change surfaces that must move together before any later implementation:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `core/artifacts/run_evidence_graph_schema.json` if node, edge, view-token, or framing vocabulary changes
3. `core/artifacts/schema_registry.yaml` if the registered contract version or artifact registration changes
4. `orket/runtime/run_evidence_graph.py`
5. `orket/runtime/run_evidence_graph_projection.py`
6. `orket/runtime/run_evidence_graph_rendering.py`
7. `scripts/observability/emit_run_evidence_graph.py`
8. `tests/runtime/test_run_evidence_graph_projection.py`
9. `tests/runtime/test_run_evidence_graph_rendering.py`
10. `tests/scripts/test_emit_run_evidence_graph.py`
11. `docs/ROADMAP.md`
12. `CURRENT_AUTHORITY.md` if the canonical operator path or authority posture changes

What remains non-normative after this lane:
1. `authority`, `decision`, `closure`, and `resource-authority` as named future family labels beyond the already-shipped normative V1 view tokens
2. any new selected-view token or operator-facing family label beyond `full_lineage`, `failure_path`, `resource_authority_path`, and `closure_path`
3. any decision-focused specialization labels or rendering taxonomies not already required by the shipped contract
4. `workload-composition` and `counterfactual/comparison`

Slice 4 outcome:
1. the Graphs requirements-hardening lane closes with explicit continued deferral rather than durable contract promotion
2. any future graph-family promotion or implementation must reopen as a new explicit roadmap lane

## Completion gate

This lane is complete only when:
1. each in-scope family has a clear operator question or an explicit defer-or-reject decision
2. each promoted family candidate has a clear decision of filtered view versus new artifact family
3. deferred families have explicit reopen criteria
4. any accepted durable contract deltas are ready to extract into `docs/specs/` before an implementation request
5. roadmap and project-index entries tell one story about the active lane
