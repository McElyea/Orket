# Graphs Authority And Decision Views Reopen Lane Closeout

Last updated: 2026-04-01
Status: Completed
Owner: Orket Core

Archived lane authority:
1. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_REQUIREMENTS.md`
2. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_IMPLEMENTATION_PLAN.md`

Historical staging ancestor:
1. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Outcome

The bounded Graphs `conditional Graphs reopen for authority and decision views only` lane is closed.

Closeout facts:
1. `run_evidence_graph` remains the only admitted graph artifact family and canonical operator path.
2. `authority` and `decision` are now admitted `run_evidence_graph` filtered-view tokens over the same semantic core rather than deferred Graphs vocabulary.
3. default operator emission without `--view` remains `full_lineage`, `failure_path`, `resource_authority_path`, and `closure_path`, so the reopen did not silently widen the default rendered surface.
4. the graph contract, operator runbook, and current-authority map now describe the same admitted-token and default-view story.
5. the roadmap now returns to maintenance-only posture instead of keeping a stale live Graphs lane open.

## Verification

Observed path: `primary`
Observed result: `success`

Executed proof:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_evidence_graph_runtime_contract.py tests/runtime/test_run_evidence_graph_projection.py tests/runtime/test_run_evidence_graph_rendering.py tests/scripts/test_emit_run_evidence_graph.py tests/contracts/test_run_evidence_graph_contract.py tests/platform/test_current_authority_map.py`
2. `python scripts/governance/check_docs_project_hygiene.py`

## Remaining Blockers Or Drift

1. No active Graphs implementation lane remains after this closeout; any future Graphs reopen must be promoted explicitly through `docs/ROADMAP.md`.
2. Workload-composition and counterfactual/comparison graphing remain out of scope and deferred.
