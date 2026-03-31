Last updated: 2026-03-30
Status: Completed
Owner: Orket Core

Active durable authority:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `CURRENT_AUTHORITY.md`

Archived implementation authority:
1. `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/RUN_EVIDENCE_GRAPH_IMPLEMENTATION_PLAN.md`

## Outcome

The additive Graph lane is closed.

Completed in this lane:
1. `run_evidence_graph.json` shipped as a separate schema-pinned artifact family from `run_graph.json`.
2. the canonical operator path `python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>` is live and authority-synced.
3. deterministic Mermaid and HTML views now derive from one semantic graph payload under `runs/<session_id>/`.
4. structural, integration, and bounded live proof passed for covered governed runs, including a real blocked governed run whose emitted graph preserved blocked terminal truth.

## Verification

Observed path: `primary`
Observed result: `success`

Executed proof:
1. `python -m pytest -q tests/contracts/test_run_evidence_graph_contract.py tests/contracts/test_run_evidence_graph_projection_validation.py tests/runtime/test_run_evidence_graph_projection.py tests/runtime/test_run_evidence_graph_rendering.py tests/scripts/test_emit_run_evidence_graph.py tests/runtime/test_run_evidence_graph_runtime_contract.py tests/runtime/test_contract_bootstrap.py tests/runtime/test_run_graph_reconstruction.py` (`28 passed`)
2. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/integration/test_sandbox_lifecycle_view_service.py tests/application/test_kernel_action_control_plane_view_service.py` (`7 passed`)
3. `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --smoke-stream` (`PREFLIGHT=PASS`)
4. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p01_single_issue.py --workspace .tmp/run_evidence_graph_live_p01 --model qwen2.5-coder:7b --output .tmp/run_evidence_graph_live_p01_report.json --json` followed by `ORKET_DISABLE_SANDBOX=1 python scripts/observability/emit_run_evidence_graph.py --run-id <fresh turn-tool-run>` (`graph_result=complete`)
5. bounded live boundary execution under `.tmp/run_evidence_graph_live_boundary` followed by `ORKET_DISABLE_SANDBOX=1 python scripts/observability/emit_run_evidence_graph.py --run-id orchestrator-issue-run:e23c2508:ISSUE-B:lead_architect:0001 --workspace-root .tmp/run_evidence_graph_live_boundary/workspace --control-plane-db .tmp/run_evidence_graph_live_boundary/control_plane_records.sqlite3` (`graph_result=complete`, emitted final truth preserved `result_class=blocked`, `closure_basis=policy_terminal_stop`)
6. `python scripts/governance/check_docs_project_hygiene.py` (pass)

## Remaining Blockers Or Drift

1. None for the accepted V1 run-evidence graph scope.
2. Future expansion of the covered-run set, including top-level cards-epic closure coverage, must reopen as a new explicit roadmap lane.

## Archived Record

1. `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/requirements.md`
2. `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/Graphs-requirements.md`
3. `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/RUN_EVIDENCE_GRAPH_IMPLEMENTATION_PLAN.md`
