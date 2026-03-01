# Volatility Baseline

Generated from `scripts/churn_report.py` on 2026-02-11.
Evidence file: `benchmarks/results/2026-02-11_phaseR_churn.json`.

## Current Hotspots (File Touches)
1. `orket/orket.py` (32)
2. `orket/tools.py` (27)
3. `orket/interfaces/api.py` (17)
4. `orket/agents/agent.py` (17)
5. `orket/schema.py` (15)
6. `orket/orchestration/orchestrator.py` (14)

## Interpretation
1. `orket/tools.py` and `orket/interfaces/api.py` remain high-volatility control points.
2. `orket/orchestration/orchestrator.py` continues as a volatile workflow coordinator.
3. Schema churn is still high enough to require stronger boundary contracts around status/shape adaptation.

## Decomposition Moves (Next)
1. Continue shrinking `orket/tools.py` by moving process-oriented tools into family-specific modules.
2. Extract API endpoint orchestration policies from `orket/interfaces/api.py` behind decision/runtime nodes.
3. Split orchestrator turn lifecycle into stable core loop + isolated turn policy adapters.

## Completed In This Slice
1. Process/governance tools extracted from `ToolBox` into `orket/tool_families/governance.py`.
2. Default tool strategy now maps governance actions through `toolbox.governance.*` instead of mixed `ToolBox` methods.
