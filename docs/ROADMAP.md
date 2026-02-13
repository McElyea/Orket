# Orket Roadmap

Last updated: 2026-02-13.

## Completed Through This Update
1. Volatility architecture baseline is in place:
   - `docs/architecture/ADR-0001-volatility-tier-boundaries.md`
   - `docs/architecture/dependency_graph_snapshot.md`
   - `docs/architecture/dependency_graph_snapshot.json`
2. Core canonical moves completed:
   - `orket/application/workflows/{orchestrator.py,turn_executor.py}`
   - `orket/application/services/{prompt_compiler.py,tool_parser.py}`
   - `orket/adapters/{llm,storage,vcs,tools}/*`
3. Coordinator/worker migration completed:
   - new canonical modules:
     - `orket/core/domain/coordinator_card.py`
     - `orket/application/services/coordinator_store.py`
     - `orket/interfaces/coordinator_api.py`
     - `orket/adapters/execution/worker_client.py`
   - legacy dirs removed:
     - `coordinator/`
     - `worker/`
4. Test architecture lanes created and running:
   - `tests/core`
   - `tests/application`
   - `tests/adapters`
   - `tests/interfaces`
   - `tests/platform`
   - `tests/integration`
   - `tests/live`
5. Current verification baseline:
   - `python -m pytest tests -q` -> 299 passed, 1 skipped
   - `python scripts/check_dependency_direction.py` -> passed
   - `python scripts/check_volatility_boundaries.py` -> passed
6. Volatility reorg P0 completed:
   - removed legacy runtime shims:
     - `orket/orchestration/{orchestrator.py,turn_executor.py}`
     - `orket/services/{prompt_compiler.py,tool_parser.py}`
     - `orket/llm.py`
     - `orket/infrastructure/*`
     - `orket/tool_runtime/*`
     - `orket/tool_strategy/*`
     - `orket/tool_families/*`
   - boundary hardening landed:
     - runtime legacy import bans in `tests/platform/test_architecture_volatility_boundaries.py`
     - application->adapters import bans in `tests/platform/test_architecture_volatility_boundaries.py`
     - CI gate command in `scripts/check_volatility_boundaries.py`
   - interface/api cleanup landed:
     - archive endpoint selector + response policy moved into `ApiRuntimeStrategyNode`
     - `orket/interfaces/api.py` now delegates archive policy branching to decision node methods

## Phase 2: Middleware + Progress Enforcement
1. Implement middleware hooks:
   - `before_prompt`
   - `after_model`
   - `before_tool`
   - `after_tool`
   - `on_turn_failure`
2. Add per-role progress contract checks.
3. Allow one corrective reprompt, then deterministic fail with reason.
4. Add coverage for hook order, short-circuit, recovery, and fail paths.

## Phase 3: Guard Workflow Formalization
1. Add explicit guard states/events:
   - `awaiting_guard_review`
   - `guard_approved`
   - `guard_rejected`
   - `guard_requested_changes`
2. Enforce guard finalization authority in transitions.
3. Add review payload schema (rationale, violations, remediation actions).
4. Add live/integration acceptance for approve and reject flows.

## Phase 4: Checkpoint/Resume + Replay
1. Persist per-turn checkpoint artifacts (run/issue/turn ids, prompt hash, model, tool calls, state deltas).
2. Add resume policy for stalled/interrupted runs.
3. Add replay command for single-turn diagnostics.
4. Guarantee idempotency on repeated tool execution during resume.

## Phase 5: Observability + CI Lane Finalization
1. Finalize event taxonomy and field schema across model/parser/tool/transition/guard.
2. Add failure-mode and non-progress reports.
3. Finalize CI lane policy:
   - define lane names (`unit`/`integration`/`acceptance`/`live`) and mapping
   - keep `live` opt-in and excluded from default CI
   - assign time budgets per lane
4. Add runbook troubleshooting flow for stalled role pipelines.

## Phase 6: Prompt Optimization Program
1. Build in-repo prompt eval harness from failing live scenarios.
2. Track:
   - tool parse rate
   - required-action completion rate
   - status progression rate
   - guard decision reach rate
3. Tune prompts on regression set until metrics stabilize.
4. Reassess PromptWizard after two optimization cycles.
5. If adopted, keep PromptWizard optional under `scripts/prompt_lab/` and never runtime-critical.

## Exit Criteria
1. Canonical tier boundaries are enforced in CI with no legacy shim paths in runtime imports.
2. Role pipeline consistently produces artifacts and reaches guard approve/reject outcomes.
3. Resume/replay produces deterministic diagnostics for stalled runs.
4. Prompt quality is measured by repeatable metrics and tracked over time.
