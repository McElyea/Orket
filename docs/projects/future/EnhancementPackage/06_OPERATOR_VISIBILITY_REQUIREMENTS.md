# Operator Visibility Requirements

Last updated: 2026-04-02
Status: Draft staged future-lane requirements
Authority status: Staging only. Not current roadmap authority. Not current execution authority until explicitly adopted.
Owner: Orket Core
Lane family: Operator surfaces and bounded graph views

## Purpose

Define a bounded operator-visibility lane that improves live inspection, replay visibility, and narrow graph work without inflating graph-family scope beyond durable runtime truth.

## Current shipped baseline

Current authority already ships a bounded operator-visibility baseline.
That baseline includes run-evidence graph support with admitted `authority` and `decision` filtered views on the shipped graph family.
This doc does not claim that those views are hypothetical or unadmitted.

## Future delta proposed by this doc

This doc proposes operator-visibility hardening beyond the shipped baseline.
Candidate deltas include:
1. a stable live event vocabulary,
2. stronger replay and diff inspection posture,
3. stronger resource and lease inspection,
4. one clearer canonical operator path and proof path for admitted views,
5. narrowly bounded new visibility surfaces only where separately justified.

## What this doc does not reopen

This doc does not reopen:
1. broad graph-family expansion,
2. composition graphs that require stronger lineage than the runtime already has,
3. counterfactual graphing unless separately contracted,
4. view-layer inventions that outrun durable source truth.

## Usage boundary

This doc should be read as a bounded visibility and operator-inspection candidate.

It should not be read as:
1. permission to reopen graph-family work broadly,
2. permission to invent lineage or causality that the runtime has not durably published,
3. permission to let views become authority,
4. a claim that `authority` and `decision` run-evidence views are still merely proposed.

## In scope

1. stable live event stream,
2. operator hold, resume, approve, and reject inspection surfaces where already admitted,
3. run diff and replay inspection,
4. resource and lease inspection,
5. hardening of already-admitted narrow graph views,
6. public operator-facing inspection APIs where explicitly selected.

## Out of scope

1. broad graph-family expansion,
2. composition graphs that require stronger lineage than the runtime already has,
3. counterfactual graphing unless separately contracted,
4. view-layer inventions that outrun durable source truth.

## Core requirements

### OV-01. Views remain read models
Operator visibility surfaces must remain read models unless a separate contract explicitly grants mutation or continuation authority.

### OV-02. Stable event vocabulary
The lane must define one stable live event vocabulary for admitted operator-visible runtime events.

### OV-03. Replay and diff stay inspection-only
Replay, diff, and reconstruction views must not silently become continuation authority.

### OV-04. Resource and lease inspection are truthful
Resource, reservation, or lease inspection surfaces must read from durable truth rather than ad hoc inference where such durable truth exists.

### OV-05. Already-admitted graph views remain the baseline
`authority` and `decision` are already admitted run-evidence views.
This lane may harden their canonical operator paths, proof paths, and surrounding visibility posture, but it must not describe them as merely possible future admissions.

### OV-06. New graph work stays narrow and explicitly justified
Any net-new graph or view work must remain tightly bounded and must state why existing admitted views are insufficient.

### OV-07. Graph reopen is explicit where required
If the repo treats graph-family work as separately gated, graph execution work beyond the shipped admitted views must not proceed without explicit reopen authority.

### OV-08. No invented lineage
Graphs and operator views must not invent parent-child, causality, approval, or resource lineage that the runtime has not durably published.

### OV-09. Canonical operator path per admitted view
Each admitted graph or inspection view must have one canonical operator path.

### OV-10. Proof path per admitted view
Each admitted graph or inspection view must have one bounded proof path.

### OV-11. View inflation is prohibited
Adding new operator views must not silently become a family-wide reopen.

## Acceptance boundary

This lane is acceptable only when:
1. the admitted event vocabulary is stable,
2. replay and diff remain inspection-only,
3. resource and lease inspection is truthful,
4. each admitted graph or inspection view has one canonical operator path,
5. each admitted graph or inspection view has one proof path,
6. graph scope remains narrow and faithful to durable truth,
7. the already-shipped graph baseline is described truthfully.

## Proof requirements

Structural proof:
1. no admitted view acts as hidden authority,
2. no graph view invents lineage absent from durable source truth,
3. no replay or diff surface implies resume by default,
4. no narrow graph admission silently expands into a broad family,
5. no adoption text understates the already-shipped graph baseline.

Integration proof:
1. at least one admitted live event stream path emits the stable vocabulary,
2. at least one replay or diff inspection path stays read-only,
3. one admitted graph view renders from durable truth,
4. one admitted resource or lease inspection path remains truthful.

Live proof where real surfaces are involved:
1. operators can inspect live or near-live event output,
2. the admitted graph view renders from existing durable truth,
3. inspection surfaces do not create continuation claims.

## Ordering note

This doc is sixth in the packet because visibility and graph work should reflect stronger underlying runtime truth rather than driving it.
