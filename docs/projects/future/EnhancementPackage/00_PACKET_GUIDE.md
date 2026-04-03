# Orket Next-Lane Requirements Packet Guide

Last updated: 2026-04-02
Status: Draft staged packet for lane selection
Authority status: Staging only. Not current roadmap authority. Not execution authority until explicitly adopted.
Owner: Orket Core

## Purpose

Capture six independent requirement-doc candidates for near-term Orket lane selection.

This packet is intentionally one level below roadmap authority.
It exists to:
1. preserve a bounded description of the six groupings,
2. keep ordering logic explicit,
3. let one grouping be adopted without silently adopting the others,
4. keep downstream product ideas separate from runtime-spine work,
5. state future deltas against already-shipped authority rather than pretending Packet 1 admissions do not exist.

## Staging posture

This packet is staging material.
It is not a current-authority surface.
It is not a formal top-level project by implication.
It must not be treated as landed repo authority merely because the docs exist.

If this packet is committed to the repo before formal adoption, it should remain under a future or staging area such as `docs/projects/future/`.
It should not be treated as a top-level execution project until the repo explicitly decides to promote it.
Its existence alone must not force a new `ROADMAP.md` project-index entry or reopen a paused lane.

## Usage boundary

This packet should be read as:
1. lane-selection input,
2. requirements staging material,
3. a bounded framing surface for future explicit reopen or adoption,
4. delta-planning material over current shipped authority.

This packet should not be read as:
1. proof that any listed lane is active,
2. permission to execute all six lanes together,
3. a claim that Packet 1 session, extension, approval, or graph admissions are unshipped,
4. a replacement for roadmap authority, current authority, accepted packet authority, or paused checkpoint authority.

## Required framing for every child doc

Every child doc in this packet must carry these three sections near the top:
1. current shipped baseline,
2. future delta proposed by this doc,
3. what this doc does not reopen.

Those sections are mandatory because the main risk in this packet is self-deception through under-truthful baselines.
A child doc is malformed if it reads like it is introducing a surface that current authority already ships in bounded form.

## Why these six groupings exist

The underlying brainstorm material converges on six coherent bundles:

1. supervisor spine,
2. session continuity,
3. extension surface,
4. runtime convergence and simplification,
5. workflow and compiler surface,
6. operator visibility.

These groupings intentionally separate:
1. runtime supervision from product work,
2. continuity primitives from UX ambitions,
3. extension packaging from marketplace ambitions,
4. simplification work from vague architecture cleanup,
5. workflow composition from unstable core seams,
6. operator visibility from broad graph-family expansion.

## Recommended ordering

The preferred order for explicit adoption is:

1. Supervisor spine
2. Session continuity
3. Extension surface
4. Runtime convergence and simplification
5. Workflow and compiler surface
6. Operator visibility

## Ordering rationale

### 1. Supervisor spine first

Approval, checkpoint, interrupt, and resume behavior remain the strongest bounded runtime-supervision move available.
The current repo already ships a bounded Packet 1 approval family.
The next useful move is a truthful delta beyond that shipped family, not a re-introduction of the family as though it does not exist.

### 2. Session continuity second

The current repo already ships a bounded host-owned session boundary.
The next useful move is to harden and extend that session spine with clearer memory-family separation, provider lineage, and cleanup posture.

### 3. Extension surface third

The current repo already ships a bounded extension validate, build, verify, and intake story.
The next useful move is to harden install, update, disable, audit, and compatibility posture without pretending the package surface is absent today.

### 4. Runtime convergence and simplification fourth

This grouping is architecturally important, but it is also the easiest one to let sprawl back into a large convergence lane.
It must remain explicitly subordinate to the paused ControlPlane checkpoint authority unless the repo formally reopens a hotter lane.

### 5. Workflow and compiler surface fifth

Declarative workflows, validation, and composition become much safer after workload authority, supervision, and continuity seams are colder.
This grouping must anchor to existing workload-authority and control-plane truth rather than becoming a shadow planner.

### 6. Operator visibility sixth

Operator visibility matters throughout, but graph-family work must stay tightly coupled to durable runtime truth.
The current repo already admits `authority` and `decision` run-evidence views.
This lane should harden and extend operator visibility without pretending those views are still hypothetical.

## Relationship rules across the six docs

1. Adoption of one grouping does not imply adoption of the others.
2. Runtime-spine groupings should usually precede product or ecosystem-facing groupings.
3. Product-significant authority must remain in the host, not in client repos or thin frontends.
4. Graph-family work stays narrow and conditional unless explicitly reopened by roadmap authority.
5. Simplification is allowed as a same-change rule inside adopted lanes, but should not silently become a second hidden lane.
6. No child doc may supersede current shipped authority or paused checkpoint authority by implication.

## Packet index

1. `01_SUPERVISOR_SPINE_REQUIREMENTS.md`
2. `02_SESSION_CONTINUITY_REQUIREMENTS.md`
3. `03_EXTENSION_SURFACE_REQUIREMENTS.md`
4. `04_RUNTIME_CONVERGENCE_AND_SIMPLIFICATION_REQUIREMENTS.md`
5. `05_WORKFLOW_AND_COMPILER_SURFACE_REQUIREMENTS.md`
6. `06_OPERATOR_VISIBILITY_REQUIREMENTS.md`

## Adoption rule

Any future execution move should:
1. name exactly which doc from this packet is being adopted,
2. restate whether the adoption is full or a bounded subset,
3. identify the shipped baseline the new lane starts from,
4. define current implementation authority separately,
5. update roadmap authority in the same change if the lane becomes active.
