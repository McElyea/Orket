# RuntimeOS Canonical Surface Cold-Down And Identity Alignment Requirements
Last updated: 2026-04-01
Status: Completed archived requirements companion
Owner: Orket Core
Lane type: RuntimeOS / canonical surface cold-down and identity alignment requirements

Paired implementation authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_IMPLEMENTATION_PLAN.md`

Closeout authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CLOSEOUT.md`

Historical staging source:
1. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Authority posture

This document is the archived scoped requirements companion for the completed RuntimeOS `canonical surface cold-down and identity alignment` lane formerly recorded in `docs/ROADMAP.md`.

It narrows the future-packet candidate to one exact outward runtime-surface family centered on the canonical `run_card(...)` execution story and the high-signal descriptive docs that currently expose competing identity signals.
It does not, by itself, authorize deeper runtime dispatch redesign, API contract redesign, extension contract redesign, or Graphs reopen work.

## Source authorities

This requirements companion is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `README.md`
5. `docs/README.md`
6. `docs/RUNBOOK.md`
7. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Purpose

Reduce wrapper debt and outward identity drift so the repo’s high-signal runtime surfaces stop competing with the already-established canonical `run_card(...)` path.

This lane exists to answer:
1. which public runtime wrappers and aliases remain admitted only as compatibility surfaces
2. how the canonical runtime card surface is described across the most operator-visible docs and CLI surfaces
3. which legacy wrapper or alias surfaces can be narrowed, demoted, or retired without inventing a broader runtime rewrite
4. what proof is required so identity cleanup does not become unverified wording churn

## Selected bounded scope

This lane is limited to:
1. the exact runtime wrapper and alias surfaces:
   - `orket/interfaces/cli.py`
   - `orket/orchestration/engine.py`
   - `orket/runtime/execution_pipeline.py`
   - `orket/extensions/runtime.py`
2. the exact high-signal descriptive surfaces:
   - `README.md`
   - `CURRENT_AUTHORITY.md`
   - `docs/README.md`
   - `docs/RUNBOOK.md`
3. bounded test and proof surfaces tied to those runtime wrappers and docs:
   - `tests/interfaces/test_cli_startup_semantics.py`
   - `tests/application/test_control_plane_workload_authority_governance.py`
   - `tests/application/test_engine_refactor.py`
   - `tests/runtime/test_extension_components.py`
4. retirement, narrowing, or explicit demotion of compatibility wrappers and alias emphasis only where the canonical path is already known
5. same-change authority sync when the selected outward runtime story changes

## Non-goals

This lane does not:
1. redesign the underlying `run_card(...)` dispatcher or workload selection behavior
2. remove compatibility wrappers without an explicit migration story or proof
3. broaden into API route redesign or extension package/publish contract work
4. perform repo-wide wording cleanup detached from the selected runtime surfaces
5. reopen Graphs or broader orchestration convergence work

## Decision lock

The following remain fixed while this lane is active:
1. the canonical public runtime execution surface remains `run_card(...)`
2. legacy wrapper or alias surfaces such as `run_epic(...)`, `run_issue(...)`, `run_rock(...)`, and CLI `--rock` are compatibility concerns only on this lane unless same-change authority updates say otherwise
3. no new runtime entrypoint or public API is admitted by implication
4. proof is required for any outward claim that a wrapper is retired, narrowed, or explicitly demoted
5. if a cleanup idea depends on deeper runtime behavior redesign, it is out of scope for this lane

## Current truthful starting point

The current surface baseline is:
1. `run_card(...)` is already the canonical public runtime execution surface in the engine, pipeline, and extension adapter paths
2. `run_epic(...)`, `run_issue(...)`, and `run_rock(...)` still survive as thin compatibility wrappers over `run_card(...)`
3. the CLI still exposes and narrates the legacy `--rock` alias explicitly
4. `README.md`, `CURRENT_AUTHORITY.md`, `docs/README.md`, and `docs/RUNBOOK.md` remain high-signal identity surfaces that can drift if wrapper and alias posture is not kept explicit

## Requirements

### CSCD-01. One selected surface family

The lane must stay bounded to one exact outward runtime-surface family centered on the canonical `run_card(...)` execution story.

That selection must name:
1. the runtime wrapper and alias files in scope
2. the descriptive docs in scope
3. the exact boundary beyond which the lane will not widen

### CSCD-02. Compatibility wrapper cold-down

The lane must define how the selected compatibility wrappers or aliases are retired, narrowed, or explicitly demoted without changing runtime truth silently.

That definition must describe:
1. which wrappers remain admitted as compatibility shims
2. which alias surfaces remain operator-visible versus demoted wording-only surfaces
3. how the canonical runtime path becomes clearer than before

### CSCD-03. Identity alignment across high-signal docs

The lane must define one outward identity story across the selected high-signal docs.

That definition must describe:
1. which command or entrypoint surfaces are canonical
2. which surfaces are compatibility-only
3. how the touched docs avoid competing supported-surface stories

### CSCD-04. Behavioral and surface proof

The lane must name proof expectations for the touched wrapper and identity family.

At minimum the proof set must cover:
1. CLI and wrapper behavior affected by any cold-down or alias change
2. canonical-wrapper governance around `run_card(...)`
3. doc-structure hygiene for the completed lane and touched project structure

### CSCD-05. Same-change update targets

If this lane changes materially, the same change must update:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_REQUIREMENTS.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_IMPLEMENTATION_PLAN.md`
4. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md` when this lane changes state
5. `CURRENT_AUTHORITY.md` when canonical runtime commands or wrapper posture changes
6. `README.md`, `docs/README.md`, and `docs/RUNBOOK.md` when the selected outward runtime story changes truthfully

## Requirements completion gate

This requirements companion is complete only when:
1. one exact canonical-surface cold-down family is selected truthfully
2. wrapper-cold-down and identity-alignment goals are explicit for that family
3. proof expectations are explicit
4. same-change update targets remain aligned

## Stop conditions

Stop and narrow scope if:
1. the lane starts reading like repo-wide brand or docs cleanup
2. wrapper retirement becomes a proxy for unbounded runtime redesign
3. proof cannot stay focused on the selected runtime wrapper and doc family
4. the work needs a broader orchestration or API contract reopen
