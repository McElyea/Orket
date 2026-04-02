# RuntimeOS Canonical Surface Cold-Down And Identity Alignment Implementation Plan
Last updated: 2026-04-01
Status: Completed archived implementation authority
Owner: Orket Core
Lane type: RuntimeOS / canonical surface cold-down and identity alignment

Paired requirements authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_REQUIREMENTS.md`

Closeout authority:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CLOSEOUT.md`

Historical staging source:
1. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

Related archived RuntimeOS lanes:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-SESSIONS-CONTEXT-PROVIDER-PIPELINE-CLOSEOUT/CLOSEOUT.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-TURN-EXECUTOR-SEAM-EXTRACTION-FACADE-REDUCTION-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This document is the archived implementation authority for the completed `canonical surface cold-down and identity alignment` lane formerly recorded in `docs/ROADMAP.md`.

The paired requirements companion remains `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_REQUIREMENTS.md`.
This lane is bounded to one outward runtime-surface family centered on the canonical `run_card(...)` execution story and its most visible wrapper and doc surfaces.

## Source authorities

This plan is bounded by:
1. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_REQUIREMENTS.md`
2. `docs/ROADMAP.md`
3. `docs/ARCHITECTURE.md`
4. `CURRENT_AUTHORITY.md`
5. `README.md`
6. `docs/README.md`
7. `docs/RUNBOOK.md`
8. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Purpose

Reduce wrapper debt and outward identity drift so the repo’s highest-signal runtime surfaces describe one canonical runtime story instead of competing entrypoints and aliases.

This lane exists to deliver:
1. one selected family of runtime wrapper and alias surfaces
2. one explicit canonical-versus-compatibility story for that family
3. one bounded cold-down or demotion of legacy wrapper and alias emphasis
4. one truthful proof set for the touched surface family

## Selected bounded scope

This lane is limited to:
1. `orket/interfaces/cli.py`
2. `orket/orchestration/engine.py`
3. `orket/runtime/execution_pipeline.py`
4. `orket/extensions/runtime.py`
5. `README.md`
6. `CURRENT_AUTHORITY.md`
7. `docs/README.md`
8. `docs/RUNBOOK.md`
9. bounded proof files directly tied to those surfaces only

## Non-goals

This lane does not:
1. redesign `run_card(...)` behavior or workload dispatch
2. perform repo-wide documentation cleanup
3. reopen API route contracts, extension package/publish contracts, or Graphs work
4. remove compatibility wrappers without proof-backed migration intent

## Current truthful starting point

The current implementation baseline is:
1. `run_card(...)` is already the canonical public runtime execution surface
2. `run_epic(...)`, `run_issue(...)`, and `run_rock(...)` still survive as thin wrappers over that canonical surface
3. the CLI and multiple high-signal docs still mention the legacy `--rock` alias and other compatibility wrappers prominently
4. the repo’s outward runtime story is therefore colder in implementation than in wording

## Current proof baseline

Current proof entrypoints around the selected surface family include:
1. `python -m pytest -q tests/interfaces/test_cli_startup_semantics.py`
2. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py`
3. `python -m pytest -q tests/application/test_engine_refactor.py`
4. `python -m pytest -q tests/runtime/test_extension_components.py`
5. `python scripts/governance/check_docs_project_hygiene.py`

## Execution plan

### Step 1 - Lock the selected surface family

Deliver:
1. one exact list of wrapper, alias, and doc files in scope
2. one explicit statement of what stays out of scope
3. one baseline map of canonical runtime surfaces versus compatibility-only surfaces

### Step 2 - Cold down compatibility emphasis

Deliver:
1. one clearer canonical-versus-compatibility story across the selected runtime wrapper surfaces
2. one bounded retirement, narrowing, or explicit demotion of legacy alias emphasis where truth already exists
3. one implementation that improves inspectability and operator expectations without widening runtime behavior scope

### Step 3 - Align high-signal docs and prove

Deliver:
1. one truthful proof set for the touched wrapper and identity family
2. one same-change docs sync across the selected high-signal descriptive surfaces
3. one lane closeout only if the selected cold-down goals are fully satisfied

## Same-change update targets

If this lane changes materially, the same change must update:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_REQUIREMENTS.md`
3. `docs/projects/archive/RuntimeOS/RTOS04012026-CANONICAL-SURFACE-COLD-DOWN-IDENTITY-ALIGNMENT-CLOSEOUT/CANONICAL_SURFACE_COLD_DOWN_IDENTITY_ALIGNMENT_IMPLEMENTATION_PLAN.md`
4. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md` when this lane changes state
5. `CURRENT_AUTHORITY.md` only if canonical runtime commands or wrapper posture changes
6. `README.md`, `docs/README.md`, and `docs/RUNBOOK.md` when the outward runtime story changes truthfully

## Lane completion gate

This lane is complete only when:
1. the selected wrapper and doc family is the only selected surface family
2. one outward identity story is explicit across the selected high-signal surfaces
3. wrapper or alias surfaces are retired, narrowed, or explicitly demoted truthfully
4. proof exists for the touched surface family
5. same-change authority docs remain aligned

## Stop conditions

Stop and narrow scope if:
1. the work starts widening beyond the selected wrapper and doc family
2. wording cleanup becomes the primary deliverable instead of canonical-surface cold-down
3. proof starts depending on unrelated runtime redesign
4. the lane cannot improve the surface without a much broader refactor than this lane admits
