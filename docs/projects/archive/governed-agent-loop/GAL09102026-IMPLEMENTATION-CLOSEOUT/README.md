# Governed Agent Loop

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-06
Last updated: 2026-09-09
Status: Archived — accepted implementation closeout
Owner: Orket Core

Execution state: All slices accepted; release boundary core 0.6.0 / SDK 0.6.0 / external 0.2.0
6A-6H are implemented and proven, including durable API/manual/scheduled/webhook wake admission,
API-owned opt-in supervision, provider-capacity claims, canonical loop/broker
dispatch, evidence-gated wake controls, composed inspection, and live
fixed-role Ollama supervisor execution plus wake-fenced effect
resolution/resume. Slice 7 clean build/install and external-package validation
are complete. Installed-artifact single/multi-model, approval/denial, restart,
and replay proof now passes after packaging the canonical prompt registry;
release reconciliation and explicit acceptance remain open.

The 2026-09-09 acceptance audit adds staged fixture delivery, partial-result
verification, durable progress policy, pause/stop, objective memory, atomic
approval resolution and real process-exit recovery. The current candidate's
proof and release blockers are recorded in `SLICE_7_ACCEPTANCE_PROOF_2026-09-09.md`.
The lane stays active until the remaining release gates and explicit acceptance
are satisfied.

## Objective

Coordinate the accepted governed continuous-agent implementation across the
public SDK, one external fixed-role local-model extension, and the Orket core
runtime without creating duplicate execution authority.

## Canonical docs

1. Project registry:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/README.md`
2. Roadmap-facing implementation plan:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`
3. SDK component plan:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_SDK_ENABLEMENT_PLAN.md`
4. External extension component plan:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_LOCAL_AGENT_EXTENSION_PLAN.md`
5. Orket core runtime component plan:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_CORE_RUNTIME_PLAN.md`
6. Slice 0 conformance and architecture evidence:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_0_CONFORMANCE_MATRIX.md`
7. Slices 1-2 implementation proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_1_2_PROOF_2026-09-07.md`
8. Slices 3-5 implementation proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_3_5_PROOF_2026-09-07.md`
9. Slice 6A durable wake-queue proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6A_PROOF_2026-09-07.md`
10. Slice 6B production-composition proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6B_PROOF_2026-09-07.md`
11. Slice 6C manual-wake transport proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6C_PROOF_2026-09-07.md`
12. Slice 6D wake-control proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6D_PROOF_2026-09-07.md`
13. Slice 6E live supervisor proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6E_PROOF_2026-09-07.md`
14. Slice 6F scheduled-wake proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6F_PROOF_2026-09-07.md`
15. Slice 6G webhook-wake proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6G_PROOF_2026-09-07.md`
16. Slice 6H wake-driven effect proof:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6H_PROOF_2026-09-07.md`
17. Slice 7 clean-package checkpoint:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_7_PACKAGING_CHECKPOINT_2026-09-07.md`
18. Slice 7 installed-runtime checkpoint:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_7_INSTALLED_RUNTIME_CHECKPOINT_2026-09-08.md`
19. Current Slice 7 acceptance reconciliation:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_7_ACCEPTANCE_PROOF_2026-09-09.md`

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
7. Slice 6A wake-queue delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICE_6A_2026-09-07.md`
8. Slice 6B production-composition delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICE_6B_2026-09-07.md`
9. Slice 6C manual-wake transport delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICE_6C_2026-09-07.md`
10. Slice 6D wake-control delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICE_6D_2026-09-07.md`
11. Slice 6F scheduled-wake delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICE_6F_2026-09-07.md`
12. Slice 6G webhook-wake delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICE_6G_2026-09-07.md`
13. Slice 6H wake-driven effect delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_SLICE_6H_2026-09-07.md`
14. Historical accepted requirements:
   `docs/projects/archive/governed-agent-loop/GAL09062026-REQUIREMENTS/GOVERNED_AGENT_LOOP_REQUIREMENTS_DEFINITION_PLAN.md`

## Execution rule

`docs/ROADMAP.md` points only to the coordinating implementation plan. The
three component plans are active workstreams whose execution order is governed
by that plan; they are not independent roadmap lanes.
