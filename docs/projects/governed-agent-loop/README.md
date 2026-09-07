# Governed Agent Loop

Date: 2026-09-06
Last updated: 2026-09-07
Status: Active project registry
Owner: Orket Core

Execution state: bounded CLI/application Slices 0-5 are implemented and proven,
including built external-package validation, live Ollama single/multi-model
execution, and issue-scoped effect approval/recovery. Slice 6 is blocked by the
recorded architectural-truth B2 lifecycle prerequisite; Slice 7 remains open.

## Objective

Coordinate the accepted governed continuous-agent implementation across the
public SDK, one external fixed-role local-model extension, and the Orket core
runtime without creating duplicate execution authority.

## Canonical docs

1. Project registry:
   `docs/projects/governed-agent-loop/README.md`
2. Roadmap-facing implementation plan:
   `docs/projects/governed-agent-loop/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`
3. SDK component plan:
   `docs/projects/governed-agent-loop/GOVERNED_AGENT_SDK_ENABLEMENT_PLAN.md`
4. External extension component plan:
   `docs/projects/governed-agent-loop/GOVERNED_LOCAL_AGENT_EXTENSION_PLAN.md`
5. Orket core runtime component plan:
   `docs/projects/governed-agent-loop/GOVERNED_AGENT_CORE_RUNTIME_PLAN.md`
6. Slice 0 conformance and architecture evidence:
   `docs/projects/governed-agent-loop/SLICE_0_CONFORMANCE_MATRIX.md`
7. Slices 1-2 implementation proof:
   `docs/projects/governed-agent-loop/SLICE_1_2_PROOF_2026-09-07.md`
8. Slices 3-5 implementation proof:
   `docs/projects/governed-agent-loop/SLICE_3_5_PROOF_2026-09-07.md`

## Durable authority

1. Contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`
2. Initial contract delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_V1_2026-09-06.md`
3. Implementation review delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_REVIEW_2026-09-06.md`
4. Slice 0 binding delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICE_0_2026-09-07.md`
5. Slices 1-2 runtime delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICES_1_2_2026-09-07.md`
6. Slices 3-5 runtime delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICES_3_5_2026-09-07.md`
7. Historical accepted requirements:
   `docs/projects/archive/governed-agent-loop/GAL09062026-REQUIREMENTS/GOVERNED_AGENT_LOOP_REQUIREMENTS_DEFINITION_PLAN.md`

## Execution rule

`docs/ROADMAP.md` points only to the coordinating implementation plan. The
three component plans are active workstreams whose execution order is governed
by that plan; they are not independent roadmap lanes.
