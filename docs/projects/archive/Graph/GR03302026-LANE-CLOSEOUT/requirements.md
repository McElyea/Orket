# Run Evidence Graph Requirements

Last updated: 2026-03-30
Status: Archived historical requirements record
Owner: Orket Core
Lane type: Additive observability artifact / archived history

## Authority posture

This document preserves the historical lane requirements record for the Graph implementation lane.

The active durable contract authority is:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`

It does not become active execution authority until the same change updates all of the following together:
1. `docs/ROADMAP.md`
2. the Graph row in the Project Index in `docs/ROADMAP.md`
3. this requirements file as the canonical lane authority path

This document is not an implementation plan.
Execution sequencing, proof batching, and slice order belong in a later implementation plan if the lane is explicitly opened.

## Source authorities

This document is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. the existing canonical `run_graph.json` contract surfaces:
   1. `core/artifacts/run_graph_schema.json`
   2. `core/artifacts/schema_registry.yaml`
   3. `orket/runtime/run_graph_reconstruction.py`
5. the current control-plane and runtime-truth authority surfaces already named in `CURRENT_AUTHORITY.md`
6. the active ControlPlane packet and paused convergence checkpoint, only where same-change authority-story sync is required

## Purpose

Define a separate additive graph artifact family that makes authoritative run evidence visually inspectable without creating a new execution authority surface.

This lane exists to produce a visible, mechanically truthful output from existing Orket runtime-truth surfaces.

The graph output must make the following visible:
1. work does not get to pretend it succeeded
2. runtime truth is inspectable
3. authority remains with durable records and governed projections rather than ad hoc logs or narrated summaries

## Existing artifact boundary

The existing canonical `run_graph.json` artifact remains unchanged.

This lane does not:
1. replace it
2. broaden it
3. reinterpret it
4. version-hop it in place
5. silently migrate its node or edge model

For this lane:
1. existing `run_graph.json` remains the protocol/tool/artifact reconstruction graph
2. this lane introduces `run_evidence_graph.json` as a separate additive artifact family for control-plane and runtime-truth evidence visualization

Any future attempt to unify or replace those two graph families must be handled as a separate migration lane with explicit replacement, versioning, registry, and proof rules.

## V1 scope

V1 is intentionally bounded.

A run is V1-covered only when all of the following are true:
1. the run is selected explicitly
2. the run already has coherent first-class primary `RunRecord` lineage
3. any emitted lower-level primary lineage for that run preserves its required parent control-plane lineage
4. the run already materializes under the canonical `runs/<session_id>/` artifact root

A `runs/<session_id>/` artifact directory alone does not make a run V1-covered.

V1 covers only:
1. one selected V1-covered run at a time
2. run evidence that can be projected from already-authoritative or already-validated sources
3. session-scoped runtime runs that satisfy the V1-covered rule above

V1 does not cover:
1. portfolio analytics
2. multi-run comparison
3. dashboard UI
4. roadmap or dependency graphing
5. backfilling old non-covered runs from prose or weak legacy surfaces
6. any attempt to make the graph itself authoritative
7. runs that lack coherent first-class primary `RunRecord` lineage even if a `runs/<session_id>/` directory exists

## Problem statement

Orket already has substantial structured runtime truth, but that truth is still primarily consumed through:
1. JSON artifacts
2. read models
3. implementation-local views

That leaves a visible-output gap:
1. operators can inspect raw authority surfaces
2. developers can reconstruct behavior from code and artifacts
3. but there is not yet one canonical evidence graph that shows how a run progressed and why Orket concluded what it concluded

## Non-goals

This lane does not:
1. create a new run-truth authority surface
2. replace durable control-plane records
3. replace existing machine-readable artifacts
4. replace, broaden, or reinterpret the existing canonical `run_graph.json` contract
5. reopen paused ControlPlane convergence work except where same-change sync is required
6. broaden into generic metrics visualization unrelated to runtime truth
7. permit free-form joins across legacy surfaces without an explicit primary-source rule
8. infer execution state from prose logs

## Decision lock

The following remain fixed:
1. graphs are projections, never primary authority
2. durable control-plane records remain authoritative where they already exist
3. runtime event artifacts remain evidence surfaces, not replacement authority
4. existing `run_graph.json` remains the deterministic protocol/tool/artifact reconstruction graph
5. this lane introduces `run_evidence_graph.json` as a separate additive artifact family
6. graph generation must fail closed on malformed or contradictory projection inputs rather than inventing coherence
7. visual output must preserve degraded, blocked, failed, uncertain, and reconciliation-driven outcomes truthfully
8. operator command, risk acceptance, attestation, observation, effect, recovery, and final truth must remain visibly distinct
9. V1 is per-run evidence visualization only
10. supplemental projections may annotate or enrich primary lineage, but may not create lineage that first-class records do not support

## Canonical artifact family

The canonical V1 artifact family is:
1. `runs/<session_id>/run_evidence_graph.json`
2. `runs/<session_id>/run_evidence_graph.mmd`
3. `runs/<session_id>/run_evidence_graph.svg` or `runs/<session_id>/run_evidence_graph.html`

V1 must not invent a second run root.

The canonical schema file for this artifact family is:
1. `core/artifacts/run_evidence_graph_schema.json`

The schema registry change for V1 is:
1. add `run_evidence_graph.json: "1.0"` to `core/artifacts/schema_registry.yaml`

Slice 1 pins the required top-level contract fields for `run_evidence_graph.json`:
1. `run_evidence_graph_schema_version`
2. `projection_only`
3. `graph_result`
4. `projection_framing`
5. `generation_timestamp`
6. `selected_views`
7. `source_summaries`
8. `issues`
9. `node_count`
10. `edge_count`
11. `nodes`
12. `edges`

Slice 1 also pins:
1. `family` as the node and edge family field
2. snake_case edge-family tokens such as `run_to_attempt` and `final_truth_to_run`
3. view tokens `full_lineage`, `failure_path`, `resource_authority_path`, and `closure_path`

## Required reviewer questions

For a selected covered run, the graph must allow a human reviewer to answer:
1. what run executed
2. which attempt or attempts existed
3. which steps occurred and in what order
4. which reservations, leases, resources, and observations were involved
5. which effects were published
6. whether recovery or reconciliation occurred
7. which terminal authority surface closed the run
8. why the run was classified as success, degraded, blocked, failed, uncertain, or reconciliation-closed

## Projection framing requirements

Every emitted graph artifact must declare:
1. `projection_only=true`
2. graph contract version
3. source authority summary
4. whether the graph is `complete`, `degraded`, or `blocked`
5. whether any expected sources were missing, malformed, contradictory, or intentionally unused
6. the selected graph view or views

The graph must never read like first-class execution authority.

## Source authority contract

The graph generator may consume only approved Orket authority or already-validated projection surfaces.

### Primary sources

Primary lineage sources for V1 are first-class control-plane records when they exist for the selected run:
1. `RunRecord`
2. `AttemptRecord`
3. `StepRecord`
4. `ReservationRecord`
5. `LeaseRecord`
6. `ResourceRecord`
7. `CheckpointRecord`
8. `CheckpointAcceptanceRecord`
9. `EffectJournalEntryRecord`
10. `RecoveryDecisionRecord`
11. `ReconciliationRecord`
12. `OperatorActionRecord`
13. `FinalTruthRecord`

### Supplemental sources

Supplemental sources may be used only for annotation, ordering detail, or explicitly projected linkage that does not replace primary lineage:
1. validated run-summary projections
2. validated run-ledger projections
3. runtime event artifacts
4. validated receipt-linked or effect-linked projection surfaces already permitted elsewhere in the repo

### Prohibited behavior

The graph generator must not:
1. infer missing execution state from prose logs
2. invent synthetic success edges to clean up a graph
3. collapse contradictory authority into a false-green path
4. let supplemental surfaces create lineage that first-class records do not support
5. treat non-authoritative legacy surfaces as authoritative because they are easier to render

## Source-to-node projection contract

The V1 node families are bounded and explicit.

### Required node families

V1 must support the following node families when present:
1. `run`
2. `attempt`
3. `step`
4. `reservation`
5. `lease`
6. `resource`
7. `observation`
8. `checkpoint`
9. `checkpoint_acceptance`
10. `effect`
11. `recovery_decision`
12. `reconciliation`
13. `operator_action`
14. `final_truth`

### Primary source mapping

The primary source-to-node mapping is:
1. `run` <- `RunRecord`
2. `attempt` <- `AttemptRecord`
3. `step` <- `StepRecord`
4. `reservation` <- `ReservationRecord`
5. `lease` <- `LeaseRecord`
6. `resource` <- `ResourceRecord`
7. `checkpoint` <- `CheckpointRecord`
8. `checkpoint_acceptance` <- `CheckpointAcceptanceRecord`
9. `effect` <- `EffectJournalEntryRecord`
10. `recovery_decision` <- `RecoveryDecisionRecord`
11. `reconciliation` <- `ReconciliationRecord`
12. `operator_action` <- `OperatorActionRecord`
13. `final_truth` <- `FinalTruthRecord`

### Observation node rule

`observation` is a bounded node family.

V1 may emit an `observation` node only when a validated source already carries an observed-world-state fact relevant to the run and that fact is already linked to the selected run's control-plane lineage.

Allowed observation-node inputs are limited to:
1. effect-journal observed-result linkage already attached to a covered run or step
2. resource observation or current-state linkage already attached to a covered resource record
3. final-truth or closure-facing authoritative result linkage already attached to a covered run
4. another validated observation ref already permitted by existing read models for the same covered run

Free-text logs must not create `observation` nodes.

## Source-to-edge projection contract

The V1 edge families are bounded and explicit.

### Required edge families

V1 must support the following edge families when present:
1. `run -> attempt`
2. `attempt -> step`
3. `attempt -> checkpoint` for first-class attempt-owned checkpoint boundaries
4. `reservation -> lease` promotion
5. `lease -> resource` authority linkage
6. `step -> checkpoint` when first-class lineage explicitly attaches the checkpoint to a step
7. `checkpoint -> checkpoint_acceptance`
8. `step -> effect`
9. `attempt -> recovery_decision`
10. `step -> observation`
11. `observation -> effect`, `observation -> resource`, or `observation -> final_truth` when a validated authority link exists
12. `reconciliation -> final_truth`
13. `operator_action -> affected transition` or `operator_action -> affected resource`
14. `final_truth -> run` closure linkage

### Supplemental edge rule

Supplemental surfaces may contribute:
1. labels
2. timestamps
3. ordering hints
4. projection-source annotations
5. already-projected artifact linkage

Supplemental surfaces may not contribute a lineage edge if the corresponding first-class lineage is absent or contradictory.

## Ordering requirements

The graph must preserve authoritative sequence where authoritative sequence exists.

If exact ordering is known:
1. it must be rendered deterministically
2. the semantic graph JSON must preserve that ordering explicitly

If exact ordering is not known:
1. the graph must say so explicitly
2. the graph must not pretend total order

Runtime events may contribute ordering annotation only when they align with the selected run's primary lineage.

## Visual-truth requirements

The graph must make all of the following visibly distinct:
1. observation versus projection
2. reservation versus active lease
3. recovery decision versus ordinary continuation
4. operator command versus operator risk acceptance versus operator attestation
5. final truth versus intermediate state
6. failed or blocked path versus successful path
7. degraded success versus clean success
8. reconciliation-closed outcomes versus ordinary completion

The rendering may use:
1. labels
2. icons
3. grouping
4. subgraphs
5. line styles

The rendering must not rely on color alone for critical meaning.

## View requirements

V1 must support multiple views over the same validated graph JSON.

Required views:
1. full lineage
2. failure path
3. resource authority path
4. closure path

These views may be:
1. separate rendered files derived from one semantic graph JSON, or
2. selectable modes declared inside the same graph contract

## Complete, degraded, and blocked rules

The graph result classification is normative.

A run that is not V1-covered is `blocked`, not `degraded`.

### Complete

Emit `complete` only when:
1. the selected run is in V1 scope
2. the primary run lineage is coherent
3. every emitted primary node family is backed by a coherent primary source
4. no emitted edge depends on missing or contradictory parent lineage
5. no selected view requires a missing distinction that would make the result misleading

### Degraded

Emit `degraded` only when:
1. the primary run lineage is still coherent enough to render a truthful graph
2. one or more supplemental sources are missing, malformed, or intentionally omitted
3. one or more optional annotations or optional node families are suppressed without changing the truthful primary lineage
4. an observation-side annotation or other supplemental detail is unavailable, but the graph can still preserve the required visible distinctions without inventing state

Examples that may degrade but not block:
1. runtime event artifacts are missing, but first-class lineage is coherent
2. run-summary or run-ledger projections are unavailable, but primary control-plane lineage is coherent
3. a requested view loses a supplemental annotation while preserving truthful first-class lineage

### Blocked

Emit `blocked` when any of the following occurs:
1. the selected run is outside V1 scope
2. no coherent primary `RunRecord` lineage exists for the selected run
3. a lower-level primary ref survives without its required parent lineage
4. an `EffectJournalEntryRecord` requires a `StepRecord` lineage that is absent or contradictory
5. a `LeaseRecord` requires promotion or authority lineage that is absent or contradictory
6. a terminal run in the covered path set lacks coherent `FinalTruthRecord` closure
7. contradictory terminal states survive after validation
8. a selected view would require the graph to invent lineage or collapse an unavailable distinction
9. an invalid projection framing would cause a supplemental surface to masquerade as authority

Blocked output may still emit a blocked artifact shell, but that artifact must state why the graph is not trustworthy.

## CLI and operator path requirements

Orket must expose one canonical operator path for generating the artifact family for a selected V1-covered run.

That path must:
1. accept canonical run selection input
2. fail closed if the run cannot be located, validated, or falls outside V1 scope
3. write the artifact family to the canonical `runs/<session_id>/` output location
4. report `complete`, `degraded`, or `blocked`
5. preserve enough machine detail for automated proof and later publication

## Artifact contract requirements

Each emitted graph artifact family must carry:
1. `run_id`
2. graph contract version
3. projection framing
4. source authority summary
5. generation timestamp
6. generation result classification
7. invalidity or degradation detail when present
8. emitted view or views
9. stable node identifiers
10. stable edge identifiers

The graph contract must be versioned explicitly.

## Determinism requirements

For the same validated authority inputs and the same rendering mode:
1. semantic graph JSON must be deterministic
2. node identifiers must be stable
3. edge identifiers must be stable
4. edge ordering must be stable where ordering is defined
5. grouping behavior must be stable
6. semantic output text must be stable apart from explicitly time-varying metadata

If layout rendering is not fully deterministic, the semantic graph JSON must still remain deterministic.

## Integration rules

This lane must reuse existing Orket authority seams where practical rather than creating parallel read models.

The implementation must preferentially reuse:
1. existing run-ledger projection and validation seams
2. existing control-plane read-model seams
3. existing run-summary validation seams where those surfaces are already permitted
4. existing run-graph reconstruction helpers only where that reuse does not broaden or reinterpret the existing `run_graph.json` contract

This is an additive artifact lane, not a new runtime authority lane.

## Same-change update rules

If this lane is opened or materially advanced, the same change must update:
1. `docs/ROADMAP.md`
2. the Graph row in the Project Index in `docs/ROADMAP.md`
3. this requirements file
4. `core/artifacts/run_evidence_graph_schema.json` when the contract lands
5. `core/artifacts/schema_registry.yaml` when the artifact is registered
6. `CURRENT_AUTHORITY.md` if the canonical operator path or canonical artifact family becomes active authority

Do not let code, schema, registry, roadmap, and authority docs drift into parallel stories.

## Proof requirements

### Structural

Structural proof must show:
1. explicit projection framing
2. bounded source-to-node mapping
3. bounded source-to-edge mapping
4. malformed or orphaned lineage fails closed
5. contradictory terminal paths are not silently merged
6. degraded outputs remain visibly degraded
7. `run_evidence_graph.json` is registered separately from the existing `run_graph.json` contract

### Integration

Integration proof must show:
1. a covered run with one attempt and terminal success renders correctly
2. a covered run with recovery renders recovery explicitly
3. a covered run with reservation, lease, and resource activity renders ownership lineage correctly
4. a covered run with reconciliation or blocked continuation renders closure truthfully
5. a malformed lower-level lineage blocks or degrades as required rather than normalizing
6. observation nodes appear only from bounded validated sources and never from free-text logs

### Live

When live proof is appropriate, it must show:
1. a real covered run can emit the artifact family
2. a real non-happy-path covered run remains truthfully non-happy in the visual output
3. emitted graph output matches authoritative terminal outcome and does not invent a clean path

## Acceptance criteria

This lane is acceptable only when all of the following are true:
1. a V1-covered run can emit the canonical run-evidence graph artifact family
2. the graph makes authoritative run progression visually inspectable
3. graph artifacts are explicitly projection-only
4. the graph reuses validated Orket truth surfaces rather than inventing a new authority seam
5. non-happy-path behavior remains visually truthful
6. malformed or contradictory evidence fails closed
7. the new artifact family is visibly distinct from the existing `run_graph.json` contract
8. the output is strong enough to serve as a signature Orket artifact rather than an internal-only debug file

## Explicit follow-on work not included in V1

The following are not part of this requirements document:
1. benchmark trend graphs
2. acceptance trend graphs
3. roadmap or dependency graphs
4. live dashboard UI
5. multi-run comparison views
6. portfolio-level operator analytics
7. any migration or replacement of the existing `run_graph.json` contract
