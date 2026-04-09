# Control-Plane Convergence Workstream 3 Closeout
Last updated: 2026-04-08
Status: Archived partial closeout artifact
Owner: Orket Core
Workstream: 3 - Effect journal default-path convergence

Closeout authority: `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`

## Objective

Record the effect-journal convergence slices already landed under Workstream 3 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. legacy protocol receipt materialization now marks run-ledger `tool_call` and `operation_result` rows as projection-only with explicit `observability.protocol_receipts.log` source instead of silently replaying those rows as native effect authority
2. governed turn-tool protocol receipt materialization now carries projected effect-journal refs for result rows when canonical turn-tool control-plane ids exist in the invocation manifest, reducing authority drift between legacy receipt replay and durable effect-journal truth
3. legacy `run_summary.json` packet-1, packet-2, and artifact-provenance subcontracts now self-identify as fact-backed `projection_only` surfaces with explicit projection sources and fail closed when that framing drifts instead of reading like native effect or closure authority
4. governance live-proof recorders for packet-1, packet-2 repair, and artifact provenance now validate legacy `run_summary.json` projection framing before consuming those summary blocks, so malformed projection semantics fail closed instead of being silently trusted during proof recording
5. live truthful-runtime proof tests now also validate legacy `run_summary.json` projection framing before trusting packet-1, packet-2, or artifact-provenance summary blocks during end-to-end verification, so malformed projection semantics fail closed instead of being silently trusted by live proof readers
6. governance live-proof recorders and live truthful-runtime proof readers now consume one shared validated legacy `run_summary.json` loader instead of each reimplementing read-and-validate logic around those packet/evidence summary blocks

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `Effect` | `partial` | `partial` | Legacy protocol receipt materialization now explicitly marks materialized run-ledger `tool_call` / `operation_result` rows as `projection_only` with source `observability.protocol_receipts.log`, governed turn-tool result rows now carry projected effect-journal ids instead of silently presenting receipt replay as native effect authority, legacy `run_summary.json` packet-1, packet-2, and artifact-provenance blocks now self-identify as fact-backed `projection_only` surfaces and fail closed when that framing drifts instead of looking like native effect or closure authority, governance live-proof recorders and live truthful-runtime proof readers now consume one shared validated legacy run-summary loader before reading those packet/evidence summary blocks, and malformed summary framing still fails closed instead of being silently trusted. Broader artifact and workload surfaces still remain. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 3 slices:
1. `orket/runtime/protocol_receipt_materializer.py`
2. `orket/runtime/run_summary.py`
3. `orket/runtime/run_summary_packet2.py`
4. `orket/runtime/run_summary_artifact_provenance.py`
5. `scripts/governance/record_truthful_runtime_packet1_live_proof.py`
6. `scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py`
7. `scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py`
8. `scripts/common/run_summary_support.py`

Representative tests changed or added:
1. `tests/runtime/test_protocol_receipt_materializer.py`
2. `tests/runtime/test_run_summary_packet1.py`
3. `tests/runtime/test_run_summary_packet2.py`
4. `tests/runtime/test_run_summary_artifact_provenance.py`
5. `tests/runtime/test_run_summary_projection_validation.py`
6. `tests/scripts/test_truthful_runtime_live_proof_summary_validation.py`
7. `tests/live/run_summary_support.py`
8. `tests/live/test_run_summary_support.py`
9. `tests/live/test_truthful_runtime_phase_c_completion_live.py`
10. `tests/live/test_truthful_runtime_phase_e_completion_live.py`
11. `tests/live/test_truthful_runtime_packet1_live.py`
12. `tests/live/test_truthful_runtime_artifact_provenance_live.py`
13. `tests/live/test_system_acceptance_pipeline.py`
14. `tests/scripts/test_common_run_summary_support.py`

Docs changed:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_3_CLOSEOUT.md`
3. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
6. `docs/specs/TRUTHFUL_RUNTIME_REPAIR_LEDGER_CONTRACT.md`
7. `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`
8. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`
9. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`

## Proof executed

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_protocol_receipt_materializer.py`
   Result: `2 passed`
2. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
3. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py tests/runtime/test_run_summary_projection_validation.py -k "projection_source or projection_only or preserves_control_plane_refs or phase_c_contract_allows_non_repair_sections or reconstruction_matches_emitted_summary or rejects_projection_blocks"`
   Result: `13 passed, 16 deselected`
4. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_truthful_runtime_live_proof_summary_validation.py`
   Result: `3 passed`
5. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/live/test_run_summary_support.py tests/live/test_truthful_runtime_phase_c_completion_live.py tests/live/test_truthful_runtime_phase_e_completion_live.py tests/live/test_truthful_runtime_packet1_live.py tests/live/test_truthful_runtime_artifact_provenance_live.py tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live`
   Result: `2 passed, 10 skipped`
6. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_common_run_summary_support.py tests/scripts/test_truthful_runtime_live_proof_summary_validation.py tests/live/test_run_summary_support.py`
   Result: `6 passed`
7. `python -m pytest -q tests/contracts/test_control_plane_effect_journal_contract.py tests/application/test_control_plane_publication_service.py tests/runtime/test_protocol_receipt_materializer.py tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py`
   Result: `47 passed in 0.31s`

## Compatibility exits

Workstream 3 compatibility exits affected by the slices recorded here:
1. `CE-04` narrowed, not closed
   Reason: legacy protocol receipt materialization now declares projection-only status explicitly on materialized run-ledger events for governed receipt replay, legacy `run_summary.json` packet-1, packet-2, and artifact-provenance blocks now also declare projection-only status explicitly with fact-backed sources and fail closed when that framing drifts, governance live-proof recorders and live truthful-runtime proof readers now both consume one shared validated legacy run-summary loader before reading those summary blocks, but `workspace/observability/<run_id>/`, broader `orket/runtime/run_summary.py` closure/read-model behavior, and other artifact/read-model surfaces still survive and the effect journal is not yet universal on every governed mutation path.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. `workspace/observability/<run_id>/`
   Reason: observability artifacts still remain useful evidence packages and replay aids, but they are not yet universally framed as projection-only across every governed path.
2. `orket/runtime/protocol_receipt_materializer.py`
   Reason: the materializer now marks run-ledger events as projection-only, but the surface still exists to bridge older receipt-heavy evidence into the append-only run ledger.
3. `orket/runtime/run_summary.py`
   Reason: runtime summary output now declares packet-1, packet-2, and artifact-provenance subcontracts as projection-only with fact-backed sources and rejects malformed projection framing, and downstream governance plus live-proof readers now also validate that framing before consuming those subcontracts, but the broader summary surface is still not lane-wide effect-authority demoted across every path.

## Remaining gaps and blockers

Workstream 3 is not complete.

Remaining gaps:
1. effect publication is still not universal across every governed mutation and closure-relevant path
2. broader legacy receipt/artifact surfaces still survive beyond the protocol receipt materializer
3. final-truth publication still is not universally consuming effect history directly
4. `CE-04` remains open
5. the representative `Slice 3A` proof set was re-verified on `2026-04-08`, so that slice no longer belongs at the front of the open convergence queue even though `CE-04` remains open

## Authority-story updates landed with these slices

The following authority docs were updated in the same slices recorded here:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
3. `CURRENT_AUTHORITY.md`

## Verdict

Workstream 3 has started with a truthful projection-only demotion of legacy protocol receipt replay and broader fail-closed handling for legacy summary-backed proof consumers, including governance recorders and live proof tests, but it is still open.

The representative `Slice 3A` proof set was re-verified on `2026-04-08` and remains truthful, so it no longer belongs at the front of the open convergence queue. The next truthful Workstream 3 work now continues through follow-on `Slice 3B`.
