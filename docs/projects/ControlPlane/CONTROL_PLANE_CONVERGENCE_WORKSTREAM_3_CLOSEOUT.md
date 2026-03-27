# Control-Plane Convergence Workstream 3 Closeout
Last updated: 2026-03-27
Status: Partial closeout artifact
Owner: Orket Core
Workstream: 3 - Effect journal default-path convergence

## Objective

Record the effect-journal convergence slices already landed under Workstream 3 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. legacy protocol receipt materialization now marks run-ledger `tool_call` and `operation_result` rows as projection-only with explicit `observability.protocol_receipts.log` source instead of silently replaying those rows as native effect authority
2. governed turn-tool protocol receipt materialization now carries projected effect-journal refs for result rows when canonical turn-tool control-plane ids exist in the invocation manifest, reducing authority drift between legacy receipt replay and durable effect-journal truth

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `Effect` | `partial` | `partial` | Legacy protocol receipt materialization now explicitly marks materialized run-ledger `tool_call` / `operation_result` rows as `projection_only` with source `observability.protocol_receipts.log`, and governed turn-tool result rows now carry projected effect-journal ids instead of silently presenting receipt replay as native effect authority. Broader artifact and workload surfaces still remain. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 3 slices:
1. `orket/runtime/protocol_receipt_materializer.py`

Representative tests changed or added:
1. `tests/runtime/test_protocol_receipt_materializer.py`

Docs changed:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_3_CLOSEOUT.md`
3. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
4. `CURRENT_AUTHORITY.md`

## Proof executed

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_protocol_receipt_materializer.py`
   Result: `2 passed`
2. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed

## Compatibility exits

Workstream 3 compatibility exits affected by the slices recorded here:
1. `CE-04` narrowed, not closed
   Reason: legacy protocol receipt materialization now declares projection-only status explicitly on materialized run-ledger events for governed receipt replay, but `workspace/observability/<run_id>/`, `orket/runtime/run_summary.py`, and broader artifact/read-model surfaces still survive and the effect journal is not yet universal on every governed mutation path.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. `workspace/observability/<run_id>/`
   Reason: observability artifacts still remain useful evidence packages and replay aids, but they are not yet universally framed as projection-only across every governed path.
2. `orket/runtime/protocol_receipt_materializer.py`
   Reason: the materializer now marks run-ledger events as projection-only, but the surface still exists to bridge older receipt-heavy evidence into the append-only run ledger.
3. `orket/runtime/run_summary.py`
   Reason: runtime summary output remains a projection surface and still is not lane-wide effect-authority demoted across every path.

## Remaining gaps and blockers

Workstream 3 is not complete.

Remaining gaps:
1. effect publication is still not universal across every governed mutation and closure-relevant path
2. broader legacy receipt/artifact surfaces still survive beyond the protocol receipt materializer
3. final-truth publication still is not universally consuming effect history directly
4. `CE-04` remains open

## Authority-story updates landed with these slices

The following authority docs were updated in the same slices recorded here:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
3. `CURRENT_AUTHORITY.md`

## Verdict

Workstream 3 has started with a truthful projection-only demotion of legacy protocol receipt replay, but it is still open.

The next truthful Workstream 3 work should push explicit projection-only framing and durable effect-journal consumption further into the remaining legacy artifact and read-model surfaces.
