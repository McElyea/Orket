# Orket Roadmap (Merged Remaining Work)

Single roadmap for remaining architecture + agent-workflow work.
Last updated: 2026-02-13.

## Scope
1. Finish volatility-tier reorganization so ownership and dependency direction are explicit.
2. Integrate patterns 1-4 (middleware, checkpoint/resume, guard HITL, observability).
3. Add prompt-eval workflow and defer full PromptWizard adoption unless needed.

## Highest Priority: Codebase Volatility Reorg Completion
Priority: P0 (current top focus)

Goal: make runtime code layout mirror the volatility architecture already established in tests.

Execution order (must complete in sequence):
1. P0.1 Application migration completion
   - Move remaining coordination/runtime flow modules into `orket/application/workflows` and `orket/application/services`.
   - Migrate call sites to canonical `orket.application.*` imports.
   - Keep temporary shims only as short-term compatibility.
2. P0.2 Adapter consolidation completion
   - Move concrete integrations into:
     - `orket/adapters/llm`
     - `orket/adapters/storage`
     - `orket/adapters/vcs`
     - `orket/adapters/tools`
   - Ensure adapters implement contracts and do not own business decisions.
3. P0.3 Interface cleanup
   - Move/align interface entry points to `orket/interfaces/*` as thin orchestration edges.
   - Remove policy/business logic leakage from interfaces.
4. P0.4 Shim retirement
   - Remove compatibility shims after all imports are migrated and tests are green.
   - Fail CI on legacy import paths once retired.

Definition of complete for this priority:
1. No production runtime modules rely on legacy orchestration/service/infrastructure paths where canonical volatility-tier paths exist.
2. Boundary tests and dependency-direction checks pass in CI.
3. Full suite passes after shim retirement.

Current progress note:
1. Production and test code imports are now largely migrated to canonical `orket.application.*` and `orket.adapters.*` paths.
2. Compatibility shims remain as controlled temporary bridges pending retirement.

## Phase 1: Architecture Governance Baseline
Status: Complete (2026-02-13)
1. Done: Added ADR for volatility tiers/import rules (`docs/architecture/ADR-0001-volatility-tier-boundaries.md`).
2. Done: Generated dependency graph snapshot (`docs/architecture/dependency_graph_snapshot.md`, `docs/architecture/dependency_graph_snapshot.json`).
3. Done: Added architecture boundary tests:
   - `application` must not import `interfaces`
   - `core` must not import `application/adapters/interfaces`
   (`tests/platform/test_architecture_volatility_boundaries.py`)
4. Done: Added CI architecture gate for volatility boundary tests (`.gitea/workflows/quality.yml`).

## Phase 2: Application Decomposition
Status: In Progress
1. Done: Moved orchestrator/turn-execution use-cases into `orket/application/workflows`:
   - `orket/application/workflows/orchestrator.py`
   - `orket/application/workflows/turn_executor.py`
2. Done: Added compatibility shims for old import paths:
   - `orket/orchestration/orchestrator.py`
   - `orket/orchestration/turn_executor.py`
3. Done: Moved coordination services to canonical application path:
   - `orket/application/services/prompt_compiler.py`
   - `orket/application/services/tool_parser.py`
   with compatibility shims retained in `orket/services/*`.
4. Done: Migrated call sites/tests to canonical `orket/application/workflows/*` imports for orchestrator/turn-executor usage.
5. Remaining: Remove temporary compatibility imports/shims when all external references are migrated. (P0.4)

## Phase 3: Middleware + Progress Enforcement
1. Implement middleware hooks:
   - `before_prompt`
   - `after_model`
   - `before_tool`
   - `after_tool`
   - `on_turn_failure`
2. Implement progress contract validator per role:
   - required actions per role-turn (e.g., file write + status transition)
3. Add one corrective reprompt on non-progress, then deterministic fail with reason.
4. Add tests for hook order, short-circuit, and non-progress recovery/failure paths.

## Phase 4: Adapter Consolidation
Status: In Progress
1. Done: Canonicalized model provider/client location under `orket/adapters/llm`:
   - `orket/adapters/llm/local_model_provider.py`
   with compatibility shim in `orket/llm.py`.
2. Done (major): Canonicalized storage adapter modules under `orket/adapters/storage`:
   - `async_card_repository.py`
   - `async_repositories.py`
   - `async_file_tools.py`
   - `sqlite_repositories.py`
   - `command_runner.py`
   with compatibility shims retained in `orket/infrastructure/*`.
3. Done: Moved vcs/webhook integrations to canonical adapter path:
   - `orket/adapters/vcs/webhook_db.py`
   - `orket/adapters/vcs/gitea_webhook_handler.py`
   with compatibility shims retained in `orket/services/*`.
4. Done: Moved tool execution adapters under `orket/adapters/tools`:
   - `orket/adapters/tools/runtime.py`
   - `orket/adapters/tools/default_strategy.py`
   - `orket/adapters/tools/families/*`
   with compatibility shims retained in `orket/tool_runtime/*`, `orket/tool_strategy/*`, `orket/tool_families/*`.
5. Remaining: Enforce contract-based boundaries between `application` and `adapters` with stricter checks and shim retirement. (P0.2/P0.4)

## Phase 5: Guard Workflow Formalization
1. Add explicit guard states/events:
   - `awaiting_guard_review`
   - `guard_approved`
   - `guard_rejected`
   - `guard_requested_changes`
2. Enforce guard finalization authority in state transitions.
3. Add review payload schema (rationale, violations, remediation actions).
4. Add end-to-end acceptance coverage for both approve and reject paths.

## Phase 6: Checkpoint/Resume + Replay
1. Persist per-turn checkpoint artifacts and metadata:
   - run/issue/turn ids
   - prompt hash
   - selected model
   - parsed tool calls
   - pre/post status deltas
2. Implement resume policy for interrupted/stalled runs.
3. Add replay/debug command for single-turn analysis.
4. Ensure idempotency on repeated tool execution during resume.

## Phase 7: Observability Operationalization
1. Finalize event taxonomy and field schema across model/parser/tool/transition/guard.
2. Add queries/reports for top failure modes and non-progress turns.
3. Add retention policy for observability artifacts.
4. Add runbook section for diagnosing stalled role pipelines.

## Phase 8: Tests/CI Lane Realignment
Status: In Progress
1. Done (partial lane split by architecture + test intent):
   - `tests/core`
   - `tests/application`
   - `tests/adapters`
   - `tests/interfaces`
   - `tests/platform`
   - `tests/integration`
   - `tests/live`
2. Remaining: finalize lane policy names and whether to collapse/alias into strict `unit/integration/acceptance/live`.
3. Remaining: configure CI jobs per lane with explicit time budgets.
4. Remaining: keep `live` tests opt-in and excluded from default CI execution.
5. Remaining: add architecture + policy checks as required pre-merge jobs (some in place; complete lane-specific coverage pending).

## Phase 9: Prompt Optimization Program
1. Build in-repo prompt eval harness using failing live scenarios.
2. Track metrics:
   - tool parse rate
   - required-action completion rate
   - status progression rate
   - guard decision reach rate
3. Tune prompts against regression set until metrics stabilize.
4. Reassess PromptWizard after two optimization cycles.
5. If adopted, keep PromptWizard optional in `scripts/prompt_lab/` (never runtime-critical).

## Exit Criteria
1. Tier boundaries are enforced in CI and reflected in folder structure.
2. Role pipeline can reliably produce artifacts and reach guard approve/reject decision.
3. Resume/replay works for stalled runs with deterministic diagnostics.
4. Prompt quality is measured by repeatable metrics, not ad-hoc observation.
