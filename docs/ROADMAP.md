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
   - `python -m pytest tests -q` -> 310 passed, 1 skipped
   - `python scripts/check_dependency_direction.py` -> passed
   - `python scripts/check_volatility_boundaries.py` -> passed
   - `python scripts/report_failure_modes.py --out benchmarks/results/failure_modes.json` -> passed
   - `python scripts/prompt_lab/eval_harness.py --out benchmarks/results/prompt_eval_metrics.json` -> passed
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

## Phase 2: Middleware + Progress Enforcement (Completed)
1. Middleware hooks implemented and wired in `TurnExecutor`:
   - `before_prompt`
   - `after_model`
   - `before_tool`
   - `after_tool`
   - `on_turn_failure`
2. Per-role progress contract checks implemented:
   - roles with declared tools must emit at least one allowed tool call per turn.
3. Corrective reprompt policy implemented:
   - one corrective reprompt, then deterministic non-progress failure.
4. Coverage added:
   - `tests/application/test_turn_executor_middleware.py`

## Phase 3: Guard Workflow Formalization (Completed)
1. Explicit guard states/events added:
   - `awaiting_guard_review`
   - `guard_approved`
   - `guard_rejected`
   - `guard_requested_changes`
2. Guard finalization authority enforced in state machine:
   - only `integrity_guard` can emit guard decision statuses and finalize `done`.
3. Review payload schema added:
   - `orket/core/domain/guard_review.py` (`rationale`, `violations`, `remediation_actions`)
4. Acceptance coverage for approve/reject flows:
   - `tests/integration/test_system_acceptance_flow.py`
   - `tests/core/test_guard_state_machine.py`

## Phase 4: Checkpoint/Resume + Replay (Completed)
1. Per-turn checkpoint artifacts persisted:
   - `checkpoint.json` includes run/issue/turn ids, prompt hash, model, tool calls, state delta.
2. Resume policy implemented:
   - stalled/interrupted issue states are re-queued to `ready` with `resume_requeue_issue` events.
3. Replay diagnostics implemented:
   - engine API: `OrchestrationEngine.replay_turn(...)`
   - CLI: `--replay-turn <run_id>:<issue_id>:<turn_index>[:role]`
4. Resume idempotency implemented:
   - tool results are persisted and replayed under `resume_mode` without re-executing tool call.

## Phase 5: Observability + CI Lane Finalization (Completed)
1. Event taxonomy finalized and documented:
   - `docs/architecture/event_taxonomy.md`
2. Failure-mode and non-progress reporting added:
   - `scripts/report_failure_modes.py`
3. CI lanes finalized:
   - npm scripts: `ci:unit`, `ci:integration`, `ci:acceptance`, `ci:live`
   - live lane remains opt-in and excluded from default lane.
   - lane policy and budgets documented in `docs/TESTING_POLICY.md`.
4. Runbook troubleshooting flow for stalled role pipelines added:
   - `docs/RUNBOOK.md`

## Phase 6: Prompt Optimization Program (Completed)
1. In-repo prompt eval harness added:
   - `scripts/prompt_lab/eval_harness.py`
2. Metrics tracked:
   - tool parse rate
   - required-action completion rate
   - status progression rate
   - guard decision reach rate
3. Prompt lab scaffolding finalized:
   - `scripts/prompt_lab/README.md`
4. PromptWizard decision:
   - remains optional and non-runtime-critical under `scripts/prompt_lab/`.

## Exit Criteria
1. Canonical tier boundaries are enforced in CI with no legacy shim paths in runtime imports.
2. Role pipeline consistently produces artifacts and reaches guard approve/reject outcomes.
3. Resume/replay produces deterministic diagnostics for stalled runs.
4. Prompt quality is measured by repeatable metrics and tracked over time.
