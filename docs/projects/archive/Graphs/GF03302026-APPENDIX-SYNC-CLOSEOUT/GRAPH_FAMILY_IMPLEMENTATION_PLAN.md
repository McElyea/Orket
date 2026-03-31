# Graph Family Implementation Plan

Last updated: 2026-03-30
Status: Completed (archived lane closeout authority)
Owner: Orket Core
Lane type: Graph-family appendix authority sync / archived closeout authority

Requirements authority:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`

Archive note:
1. This narrow Graphs reopen packet closed on 2026-03-30.
2. Closeout authority: `docs/projects/archive/Graphs/GF03302026-APPENDIX-SYNC-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This document is the archived execution authority for a narrow Graphs reopen packet that corrected post-closeout authority wording drift in the active `run_evidence_graph` contract.

It did not reopen graph-family requirements hardening as an active product lane.
It did not reopen runtime, schema, registry, or operator-path implementation work.

The original Graphs requirements-hardening lane remains archived at:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`

## Source authorities

This narrow reopen packet was bounded by:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `docs/ROADMAP.md`
3. `docs/README.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
6. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/CLOSEOUT.md`
7. `docs/architecture/CONTRACT_DELTA_RUN_EVIDENCE_GRAPH_V1_APPENDIX_SYNC_2026-03-30.md`

## Purpose

Close the remaining Graphs authority drift after the original lane closeout by making the active `run_evidence_graph` contract speak truthfully about the Graphs archive posture.

This packet answered one bounded execution question:
1. can the active V1 contract keep the same non-normative Appendix A substance while removing stale wording that still described the archived Graphs lane as active

## Decision lock

The following remained fixed while this packet executed:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` stayed the active durable contract authority
2. the Graphs lane remained archived rather than reopened as an active feature lane
3. no runtime, schema, registry, or operator-path changes were in scope
4. Appendix A remained non-normative
5. the roadmap returned to and stayed in maintenance-only posture

## Execution checkpoint

As of 2026-03-30:
1. the stale Appendix A posture lines were rewritten to reference the archived 2026-03-30 Graphs lane rather than an active lane
2. the corresponding contract-delta note was recorded
3. the docs index was updated so the new contract-delta note remains discoverable
4. no active doc continues to describe `docs/projects/Graphs/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md` as an active path

## Execution order

### Slice 1 - Appendix posture sync

Status:
1. complete on 2026-03-30

Objective:
1. remove stale active-lane wording from Appendix A of the active `run_evidence_graph` contract without broadening the contract

Primary touchpoints:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `docs/README.md`
3. `docs/architecture/CONTRACT_DELTA_RUN_EVIDENCE_GRAPH_V1_APPENDIX_SYNC_2026-03-30.md`

Required deliverables:
1. Appendix A posture lines reference the archived Graphs lane truthfully
2. a contract-delta note records the authority sync
3. docs discovery remains aligned

Representative proof commands:
1. `python scripts/governance/check_docs_project_hygiene.py`
2. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_evidence_graph_rendering.py tests/runtime/test_run_evidence_graph_projection.py tests/scripts/test_emit_run_evidence_graph.py`

Slice exit condition:
1. the active spec, roadmap posture, and Graphs archive story tell one story

## Completion gate

This packet is complete only when:
1. Appendix A no longer describes the archived Graphs lane as active
2. the active spec remains non-normative in the same places as before
3. the docs index includes the new contract-delta note
4. docs hygiene and targeted run-evidence graph tests remain green
